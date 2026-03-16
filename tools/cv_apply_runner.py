"""Checkpointed stage runner for /cv-apply.

Hybrid architecture:
- Keep .claude/commands/cv-apply.md as UX contract.
- Use this runner for deterministic orchestration, checkpoint/resume, retries,
  invalidations, and metrics logging.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from check_pdf_pages import get_page_count
from cv_apply_contract import (
    ARTIFACT_DEFAULT_PATHS,
    CHECKPOINT_SCHEMA_VERSION,
    DEFAULT_CHECKPOINT_PATH,
    DEFAULT_METRICS_LOG,
    STAGE_ORDER,
    stage_index,
    stages_to_invalidate,
)
from docx_to_pdf import convert as convert_docx_to_pdf
from evidence_select import build_evidence
from fact_patch import apply_patch_if_safe, classify_feedback
from slot_plan import build_slot_plan
from update_db import persist_cv_paths
from validate_cv_output import validate as validate_cv_output


MAX_STAGE_RETRIES = 2


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _load_keywords(path: Path) -> dict[str, list[str]]:
    raw = _load_json(path, default={})
    source = raw.get("keywords", raw) if isinstance(raw, dict) else {}
    return {
        "required": list(source.get("required", [])),
        "nice_to_have": list(source.get("nice_to_have", [])),
    }


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


@dataclass
class RunnerArgs:
    checkpoint: Path
    metrics_log: Path
    resume: bool
    target_stage: str | None
    meta_path: Path
    keywords_path: Path
    work_exp_path: Path
    store_path: Path
    cache_path: Path
    project_selections_path: Path
    template_map_path: Path
    selections_path: Path
    feedback_path: Path | None
    patch_json: Path | None
    docx_path: str | None
    pdf_path: str | None


class StageBlockedError(RuntimeError):
    """Raised when user input or external output is required."""


class CVApplyRunner:
    def __init__(self, args: RunnerArgs):
        self.args = args
        self.ckpt = self._load_checkpoint()
        self.handlers: dict[str, Callable[[], dict[str, Any] | None]] = {
            "job_select": self.stage_job_select,
            "jd_extract": self.stage_jd_extract,
            "source_load": self.stage_source_load,
            "project_select": self.stage_project_select,
            "gap_detect": self.stage_gap_detect,
            "gap_normalize": self.stage_gap_normalize,
            "evidence_select": self.stage_evidence_select,
            "slot_plan": self.stage_slot_plan,
            "draft_work_experience": self.stage_draft_work_experience,
            "draft_technical_projects": self.stage_draft_technical_projects,
            "assemble": self.stage_assemble,
            "validate_deterministic": self.stage_validate_deterministic,
            "render_docx_pdf": self.stage_render_docx_pdf,
            "layout_gate_2pages": self.stage_layout_gate_2pages,
            "preview_feedback": self.stage_preview_feedback,
            "feedback_classify": self.stage_feedback_classify,
            "fact_patch_apply": self.stage_fact_patch_apply,
            "targeted_regen": self.stage_targeted_regen,
            "persist_db": self.stage_persist_db,
            "cover_letter_handoff": self.stage_cover_letter_handoff,
        }

    def _default_checkpoint(self) -> dict[str, Any]:
        return {
            "schema_version": CHECKPOINT_SCHEMA_VERSION,
            "step_completed": 0,
            "current_stage": "",
            "completed_stages": [],
            "artifacts": {},
            "retry_state": {},
            "invalidations": [],
            "feedback_events": [],
            "fact_patch_refs": [],
            "render_outputs": {},
            "layout_report": {},
            "error": "",
            "updated_at": _utcnow(),
        }

    def _load_checkpoint(self) -> dict[str, Any]:
        existing = _load_json(self.args.checkpoint)
        if not existing:
            ckpt = self._default_checkpoint()
            _write_json(self.args.checkpoint, ckpt)
            return ckpt
        # Forward-compatible merge with defaults.
        merged = self._default_checkpoint()
        merged.update(existing)
        if "artifacts" in existing and isinstance(existing["artifacts"], dict):
            merged["artifacts"].update(existing["artifacts"])
        return merged

    def _save_checkpoint(self) -> None:
        self.ckpt["updated_at"] = _utcnow()
        _write_json(self.args.checkpoint, self.ckpt)

    def _stage_metric(self, stage: str, status: str, attempts: int, started_at: float) -> None:
        payload = {
            "timestamp": _utcnow(),
            "stage": stage,
            "status": status,
            "attempts": attempts,
            "wall_time_ms": int((time.time() - started_at) * 1000),
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "invalidated_stage_count": len(self.ckpt.get("invalidations", [])),
            "layout_iterations": self.ckpt.get("layout_report", {}).get("iterations", 0),
            "factual_patch_count": len(self.ckpt.get("fact_patch_refs", [])),
        }
        _append_jsonl(self.args.metrics_log, payload)

    def _complete_stage(self, stage: str, output: dict[str, Any] | None) -> None:
        idx = stage_index(stage) + 1
        self.ckpt["step_completed"] = max(self.ckpt.get("step_completed", 0), idx)
        self.ckpt["current_stage"] = stage
        completed = self.ckpt.setdefault("completed_stages", [])
        if stage not in completed:
            completed.append(stage)
        if output:
            self.ckpt["artifacts"].update(output)
        self.ckpt["error"] = ""
        self._save_checkpoint()

    def _record_error(self, stage: str, error: str) -> None:
        self.ckpt["current_stage"] = stage
        self.ckpt["error"] = error
        self._save_checkpoint()

    def run(self) -> None:
        if self.args.target_stage and self.args.target_stage not in STAGE_ORDER:
            raise SystemExit(f"Unknown target stage: {self.args.target_stage}")

        start_idx = self.ckpt.get("step_completed", 0) if self.args.resume else 0
        if start_idx >= len(STAGE_ORDER):
            print(json.dumps({"ok": True, "message": "All stages already completed"}))
            return
        target_idx = stage_index(self.args.target_stage) if self.args.target_stage else len(STAGE_ORDER) - 1

        for idx in range(start_idx, target_idx + 1):
            stage = STAGE_ORDER[idx]
            handler = self.handlers[stage]
            started = time.time()
            attempts = 0
            while attempts <= MAX_STAGE_RETRIES:
                try:
                    output = handler() or {}
                    self._complete_stage(stage, output)
                    self._stage_metric(stage, "ok", attempts + 1, started)
                    break
                except StageBlockedError as exc:
                    self._record_error(stage, str(exc))
                    self._stage_metric(stage, "blocked", attempts + 1, started)
                    print(json.dumps({"ok": False, "stage": stage, "blocked": True, "error": str(exc)}))
                    return
                except Exception as exc:  # pylint: disable=broad-except
                    attempts += 1
                    retry_state = self.ckpt.setdefault("retry_state", {})
                    retry_state[stage] = attempts
                    if attempts > MAX_STAGE_RETRIES:
                        self._record_error(stage, f"{type(exc).__name__}: {exc}")
                        self._stage_metric(stage, "failed", attempts, started)
                        print(json.dumps({"ok": False, "stage": stage, "error": str(exc)}))
                        return
            # Continue to next stage on success.

        print(json.dumps({"ok": True, "step_completed": self.ckpt.get("step_completed", 0)}))

    # Stage handlers
    def stage_job_select(self) -> dict[str, Any]:
        meta = _load_json(self.args.meta_path)
        if not meta:
            raise StageBlockedError(f"Missing job meta file: {self.args.meta_path}")
        required = ("job_id", "company", "job_title")
        missing = [k for k in required if k not in meta]
        if missing:
            raise StageBlockedError(f"job_meta missing required keys: {missing}")
        return {"job_meta": meta}

    def stage_jd_extract(self) -> dict[str, Any]:
        if not self.args.keywords_path.exists():
            raise StageBlockedError(f"Missing jd keywords file: {self.args.keywords_path}")
        jd_keywords = _load_json(self.args.keywords_path)
        parsed = _load_keywords(self.args.keywords_path)
        if not parsed["required"]:
            raise StageBlockedError("JD keywords required list is empty; run keyword extraction first")
        return {"jd_keywords": jd_keywords}

    def stage_source_load(self) -> dict[str, Any]:
        for path in (self.args.work_exp_path, self.args.store_path):
            if not path.exists():
                raise StageBlockedError(f"Missing source file: {path}")
        work_exp = _load_json(self.args.work_exp_path, default={})
        store = _load_json(self.args.store_path, default={})
        cache = _load_json(self.args.cache_path, default={})
        snapshot = {
            "work_roles": len(work_exp.get("work_experience", [])),
            "projects": len(store.get("projects", [])),
            "cache_entries": len(cache),
        }
        return {"source_snapshot": snapshot}

    def stage_project_select(self) -> dict[str, Any]:
        if not self.args.project_selections_path.exists():
            raise StageBlockedError(f"Missing project selections file: {self.args.project_selections_path}")
        selections = _load_json(self.args.project_selections_path, default={})
        return {"project_selections": selections}

    def stage_gap_detect(self) -> dict[str, Any]:
        jd_keywords = self.ckpt["artifacts"].get("jd_keywords") or _load_json(self.args.keywords_path, {})
        keywords = jd_keywords.get("keywords", jd_keywords)
        required = [str(k) for k in keywords.get("required", [])]
        store = _load_json(self.args.store_path, default={})
        cache = _load_json(self.args.cache_path, default={})

        covered = set()
        for project in store.get("projects", []):
            for bullet in project.get("bullets", []):
                for kw in bullet.get("keywords_matched", []):
                    covered.add(str(kw).lower())
        for item in cache.values():
            answer = str(item.get("answer", "")).lower()
            for kw in required:
                if kw.lower() in answer:
                    covered.add(kw.lower())

        job_meta = self.ckpt["artifacts"].get("job_meta", {})
        job_id = job_meta.get("job_id", "unknown")
        questions = []
        for kw in required:
            if kw.lower() not in covered:
                questions.append(
                    {
                        "question_id": f"ad_hoc_{kw.lower().replace(' ', '_')}_{job_id}",
                        "keyword": kw,
                        "question": f"Do you have any experience with {kw}? If so, describe briefly.",
                    }
                )
        return {"gap_questions": questions}

    def stage_gap_normalize(self) -> dict[str, Any]:
        cache = _load_json(self.args.cache_path, default={})
        normalized = []
        jd_keywords = self.ckpt["artifacts"].get("jd_keywords") or _load_json(self.args.keywords_path, {})
        keywords = jd_keywords.get("keywords", jd_keywords)
        required = [str(k) for k in keywords.get("required", [])]

        for key, value in cache.items():
            answer = value.get("answer")
            if not answer:
                continue
            lowered = str(answer).lower()
            matched = [kw for kw in required if kw.lower() in lowered]
            normalized.append(
                {
                    "fact_id": f"norm_{key}",
                    "entity": key.split("_")[0],
                    "fact_text": answer,
                    "keywords_supported": matched,
                    "scope": "job_local_enrichment",
                    "confidence": "medium",
                    "job_scope": value.get("job_id"),
                    "conflicts_with": [],
                }
            )
        return {"normalized_facts": normalized}

    def stage_evidence_select(self) -> dict[str, Any]:
        work_exp = _load_json(self.args.work_exp_path, default={})
        store = _load_json(self.args.store_path, default={})
        keywords = _load_keywords(self.args.keywords_path)
        project_selections = _load_json(self.args.project_selections_path, default={})
        template_map = _load_json(self.args.template_map_path, default={})
        evidence = build_evidence(
            work_exp=work_exp,
            store=store,
            keywords=keywords,
            selections=project_selections,
            template_map=template_map,
        )
        _write_json(ARTIFACT_DEFAULT_PATHS["evidence_packs"], evidence)
        return {"evidence_packs": evidence}

    def stage_slot_plan(self) -> dict[str, Any]:
        evidence = self.ckpt["artifacts"].get("evidence_packs")
        if not evidence:
            evidence = _load_json(ARTIFACT_DEFAULT_PATHS["evidence_packs"])
        template_map = _load_json(self.args.template_map_path, default={})
        previous = self.ckpt["artifacts"].get("slot_plan")
        plan = build_slot_plan(evidence=evidence, template_map=template_map)
        _write_json(ARTIFACT_DEFAULT_PATHS["slot_plan"], plan)
        if previous and previous != plan:
            self.ckpt.setdefault("invalidations", []).extend(stages_to_invalidate("slot_plan"))
        if not plan.get("is_sufficient", False):
            raise StageBlockedError(
                "slot_plan is insufficient; ask insufficiency_questions, update cache, then resume from evidence_select"
            )
        return {"slot_plan": plan}

    def stage_draft_work_experience(self) -> dict[str, Any]:
        selections = _load_json(self.args.selections_path)
        if not selections:
            raise StageBlockedError(f"Missing draft selections: {self.args.selections_path}")
        work = [b for b in selections.get("approved_bullets", []) if b.get("section") == "work_experience"]
        if not work:
            raise StageBlockedError("No work_experience bullets found; run writer for work section")
        return {"draft_work_count": len(work)}

    def stage_draft_technical_projects(self) -> dict[str, Any]:
        selections = _load_json(self.args.selections_path)
        if not selections:
            raise StageBlockedError(f"Missing draft selections: {self.args.selections_path}")
        proj = [b for b in selections.get("approved_bullets", []) if b.get("section") == "technical_projects"]
        if not proj:
            raise StageBlockedError("No technical_projects bullets found; run writer for projects section")
        return {"draft_project_count": len(proj)}

    def stage_assemble(self) -> dict[str, Any]:
        selections = _load_json(self.args.selections_path)
        if not selections:
            raise StageBlockedError("Cannot assemble without selections output")
        return {"draft_sections": selections}

    def stage_validate_deterministic(self) -> dict[str, Any]:
        selections = _load_json(self.args.selections_path)
        slot_plan = self.ckpt["artifacts"].get("slot_plan") or _load_json(ARTIFACT_DEFAULT_PATHS["slot_plan"])
        work_exp = _load_json(self.args.work_exp_path, default={})
        report = validate_cv_output(selections=selections, slot_plan=slot_plan, work_exp=work_exp)
        if not report.get("ok", False):
            raise StageBlockedError("Deterministic validation failed; fix failed bullets and resume")
        return {"validated_bullets": report}

    def stage_render_docx_pdf(self) -> dict[str, Any]:
        docx_path = self.args.docx_path
        pdf_path = self.args.pdf_path
        if not docx_path:
            completed = subprocess.run([sys.executable, "render_cv.py"], check=False, capture_output=True, text=True)
            if completed.returncode != 0:
                raise StageBlockedError(f"render_cv failed: {completed.stderr.strip()}")
            docx_path = completed.stdout.strip().splitlines()[-1].strip()
        if not pdf_path:
            pdf_path = str(convert_docx_to_pdf(docx_path))

        outputs = {"docx_path": docx_path, "pdf_path": pdf_path}
        return {"render_outputs": outputs}

    def stage_layout_gate_2pages(self) -> dict[str, Any]:
        render_outputs = self.ckpt["artifacts"].get("render_outputs")
        if not render_outputs:
            raise StageBlockedError("render_outputs missing; run render_docx_pdf first")
        pdf_path = Path(render_outputs["pdf_path"])
        pages = get_page_count(pdf_path)
        report = {"pdf_path": str(pdf_path), "pages": pages, "exact_2pages": pages == 2, "iterations": 0}
        if pages != 2:
            raise StageBlockedError(f"Layout gate failed: expected 2 pages, got {pages}")
        self.ckpt["layout_report"] = report
        return {"layout_report": report}

    def stage_preview_feedback(self) -> dict[str, Any]:
        if not self.args.feedback_path:
            return {"preview_feedback": {"status": "no_feedback"}}
        if not self.args.feedback_path.exists():
            raise StageBlockedError(f"Feedback file not found: {self.args.feedback_path}")
        feedback_text = self.args.feedback_path.read_text(encoding="utf-8-sig").strip()
        event = {"timestamp": _utcnow(), "feedback": feedback_text}
        self.ckpt.setdefault("feedback_events", []).append(event)
        return {"preview_feedback": {"status": "captured"}}

    def stage_feedback_classify(self) -> dict[str, Any]:
        events = self.ckpt.get("feedback_events", [])
        if not events:
            return {"feedback_classification": {"feedback_type": "none"}}
        latest = events[-1]
        feedback_type = classify_feedback(latest.get("feedback", ""))
        artifact = {"feedback_type": feedback_type, "feedback_text": latest.get("feedback", "")}
        if feedback_type == "style_priority":
            self.ckpt.setdefault("invalidations", []).extend(stages_to_invalidate("feedback_classify_style"))
        return {"feedback_classification": artifact}

    def stage_fact_patch_apply(self) -> dict[str, Any]:
        classification = self.ckpt["artifacts"].get("feedback_classification", {})
        feedback_type = classification.get("feedback_type")
        if feedback_type not in {"factual_correction", "missing_fact", "overstated_scope"}:
            return {"fact_patch_result": {"skipped": True}}
        if not self.args.patch_json or not self.args.patch_json.exists():
            raise StageBlockedError("Factual feedback detected but patch json not provided")
        patch = _load_json(self.args.patch_json, default={})
        ok, reason = apply_patch_if_safe(
            patch=patch,
            work_exp_path=self.args.work_exp_path,
            project_store_path=self.args.store_path,
        )
        patch["applied"] = ok
        patch["timestamp"] = patch.get("timestamp", _utcnow())
        patch["feedback_type"] = feedback_type
        _append_jsonl(Path(r"C:\Code\CV_crawl\.cv-fact-patches.jsonl"), patch)
        refs = self.ckpt.setdefault("fact_patch_refs", [])
        refs.append({"patch_id": patch.get("patch_id", ""), "applied": ok, "reason": reason})
        if ok:
            self.ckpt.setdefault("invalidations", []).extend(stages_to_invalidate("fact_patch_apply"))
        return {"fact_patch_result": {"ok": ok, "reason": reason, "patch_id": patch.get("patch_id")}}

    def stage_targeted_regen(self) -> dict[str, Any]:
        invalidated = sorted(set(self.ckpt.get("invalidations", [])), key=stage_index)
        if invalidated:
            return {"targeted_regen": {"invalidated_stages": invalidated}}
        return {"targeted_regen": {"invalidated_stages": []}}

    def stage_persist_db(self) -> dict[str, Any]:
        job_meta = self.ckpt["artifacts"].get("job_meta")
        render_outputs = self.ckpt["artifacts"].get("render_outputs")
        if not job_meta or not render_outputs:
            raise StageBlockedError("persist_db requires job_meta and render_outputs")
        result = persist_cv_paths(
            meta=job_meta,
            docx_path=render_outputs["docx_path"],
            pdf_path=render_outputs["pdf_path"],
        )
        return {"persist_db": result}

    def stage_cover_letter_handoff(self) -> dict[str, Any]:
        job_meta = self.ckpt["artifacts"].get("job_meta", {})
        jd_keywords = self.ckpt["artifacts"].get("jd_keywords", {})
        outputs = self.ckpt["artifacts"].get("render_outputs", {})
        work_exp = _load_json(self.args.work_exp_path, default={})
        cache = _load_json(self.args.cache_path, default={})
        handoff = {
            "company": job_meta.get("company"),
            "job_title": job_meta.get("job_title"),
            "job_id": job_meta.get("job_id"),
            "keywords": jd_keywords.get("keywords", jd_keywords),
            "work_exp": work_exp,
            "experience_cache": cache,
            "docx_path": outputs.get("docx_path"),
            "pdf_path": outputs.get("pdf_path"),
        }
        handoff_path = Path(r"C:\Code\CV_crawl\.cv-apply-cover-letter-handoff.json")
        _write_json(handoff_path, handoff)
        return {"cover_letter_handoff": {"path": str(handoff_path)}}


def parse_args() -> RunnerArgs:
    parser = argparse.ArgumentParser(description="Checkpointed stage runner for /cv-apply")
    parser.add_argument("--checkpoint", default=str(DEFAULT_CHECKPOINT_PATH))
    parser.add_argument("--metrics-log", default=str(DEFAULT_METRICS_LOG))
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--target-stage")
    parser.add_argument("--meta-path", default=str(ARTIFACT_DEFAULT_PATHS["meta"]))
    parser.add_argument("--keywords-path", default=str(ARTIFACT_DEFAULT_PATHS["jd_keywords"]))
    parser.add_argument("--work-exp-path", default=r"C:\Code\CV_crawl\.cv-work-experience.json")
    parser.add_argument("--store-path", default=r"C:\Code\CV_crawl\.cv-harvest-store.json")
    parser.add_argument("--cache-path", default=r"C:\Code\CV_crawl\.experience-cache.json")
    parser.add_argument("--project-selections-path", default=str(ARTIFACT_DEFAULT_PATHS["project_selections"]))
    parser.add_argument("--template-map-path", default=r"C:\Code\CV_CoverLetter_Generator_Agentic_Pipeline\job-pipeline\profile\template_map.json")
    parser.add_argument("--selections-path", default=str(ARTIFACT_DEFAULT_PATHS["draft_sections"]))
    parser.add_argument("--feedback-path")
    parser.add_argument("--patch-json")
    parser.add_argument("--docx-path")
    parser.add_argument("--pdf-path")
    ns = parser.parse_args()
    return RunnerArgs(
        checkpoint=Path(ns.checkpoint),
        metrics_log=Path(ns.metrics_log),
        resume=ns.resume,
        target_stage=ns.target_stage,
        meta_path=Path(ns.meta_path),
        keywords_path=Path(ns.keywords_path),
        work_exp_path=Path(ns.work_exp_path),
        store_path=Path(ns.store_path),
        cache_path=Path(ns.cache_path),
        project_selections_path=Path(ns.project_selections_path),
        template_map_path=Path(ns.template_map_path),
        selections_path=Path(ns.selections_path),
        feedback_path=Path(ns.feedback_path) if ns.feedback_path else None,
        patch_json=Path(ns.patch_json) if ns.patch_json else None,
        docx_path=ns.docx_path,
        pdf_path=ns.pdf_path,
    )


def main() -> None:
    args = parse_args()
    runner = CVApplyRunner(args)
    runner.run()


if __name__ == "__main__":
    main()
