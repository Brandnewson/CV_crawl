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
    BULLET_POLICY,
    CANONICAL_FACT_STORES,
    CHECKPOINT_SCHEMA_VERSION,
    CV_FORMAT_PROFILES,
    DEFAULT_CHECKPOINT_PATH,
    DEFAULT_FACT_PATCH_LOG,
    DEFAULT_METRICS_LOG,
    REPO_ROOT,
    STAGE_ORDER,
    stage_index,
    stages_to_invalidate,
)
from coverage_plan import build_coverage_plan
from docx_to_pdf import convert as convert_docx_to_pdf
from evidence_select import build_evidence
from fact_patch import apply_patch_if_safe, classify_feedback
from reconcile_slot_plan_targets import reconcile_slot_plan_targets
from slot_plan import build_slot_plan
from update_db import persist_cv_paths
from validate_cv_output import validate as validate_cv_output
from wrap_optimizer import detect_wrapped_bullets, rephrase_wrapped_bullets


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
    coverage_review_path: Path
    cv_length_pages: int | None
    template_path: Path | None
    template_map_path: Path | None
    expected_pages: int | None
    insert_page_break_before_technical_projects: bool | None
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
            "coverage_plan": self.stage_coverage_plan,
            "coverage_review": self.stage_coverage_review,
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

    def _has_cli_cv_overrides(self) -> bool:
        return any(
            (
                self.args.cv_length_pages is not None,
                self.args.template_path is not None,
                self.args.template_map_path is not None,
                self.args.expected_pages is not None,
                self.args.insert_page_break_before_technical_projects is not None,
            )
        )

    def _resolve_cv_format_profile(self, meta: dict[str, Any] | None = None) -> dict[str, Any]:
        meta = meta or {}

        cv_length_pages: int
        if self.args.cv_length_pages is not None:
            cv_length_pages = int(self.args.cv_length_pages)
        elif str(meta.get("cv_length_pages", "")).strip() in {"1", "2"}:
            cv_length_pages = int(meta["cv_length_pages"])
        else:
            cv_length_pages = 2

        if cv_length_pages not in CV_FORMAT_PROFILES:
            cv_length_pages = 2
        profile_defaults = CV_FORMAT_PROFILES[cv_length_pages]

        template_path = self.args.template_path or profile_defaults["template_path"]
        template_map_path = self.args.template_map_path or profile_defaults["template_map_path"]
        expected_pages = (
            int(self.args.expected_pages)
            if self.args.expected_pages is not None
            else int(profile_defaults["expected_pages"])
        )
        if self.args.insert_page_break_before_technical_projects is None:
            insert_break = bool(profile_defaults["insert_page_break_before_technical_projects"])
        else:
            insert_break = bool(self.args.insert_page_break_before_technical_projects)

        return {
            "profile_name": profile_defaults["name"],
            "cv_length_pages": cv_length_pages,
            "template_path": str(Path(template_path)),
            "template_map_path": str(Path(template_map_path)),
            "expected_pages": expected_pages,
            "insert_page_break_before_technical_projects": insert_break,
            "bullet_length_min": int(profile_defaults["bullet_length_min"]),
            "bullet_length_hard_max": int(BULLET_POLICY["hard_max_chars"]),
            "bullet_length_max": int(profile_defaults["bullet_length_max"]),
            "bullet_length_target": int(BULLET_POLICY["preferred_target_chars"]),
            "explicit_coverage_ratio": float(BULLET_POLICY["explicit_coverage_ratio"]),
            "wrap_retry_budget": int(BULLET_POLICY["wrap_retry_budget"]),
        }

    def _ensure_cv_format_profile(self, meta: dict[str, Any] | None = None) -> dict[str, Any]:
        existing = self.ckpt.get("artifacts", {}).get("cv_format_profile")
        if existing and not self._has_cli_cv_overrides():
            return existing

        profile = self._resolve_cv_format_profile(meta=meta)
        self.ckpt.setdefault("artifacts", {})["cv_format_profile"] = profile
        if meta is not None:
            meta["cv_length_pages"] = profile["cv_length_pages"]
            _write_json(self.args.meta_path, meta)
        self._save_checkpoint()
        return profile

    def _ensure_cv_variant_id(self, meta: dict[str, Any]) -> str:
        existing = str(meta.get("cv_variant_id", "")).strip()
        if existing:
            return existing
        generated = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
        meta["cv_variant_id"] = generated
        _write_json(self.args.meta_path, meta)
        return generated

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
        if int(existing.get("schema_version", 0)) != CHECKPOINT_SCHEMA_VERSION:
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

    def _current_cv_profile(self) -> dict[str, Any]:
        return self.ckpt["artifacts"].get("cv_format_profile") or self._ensure_cv_format_profile()

    @staticmethod
    def _length_limits(cv_format_profile: dict[str, Any]) -> dict[str, int]:
        return {
            "min": int(cv_format_profile.get("bullet_length_min", 80)),
            "target": int(cv_format_profile.get("bullet_length_target", BULLET_POLICY["preferred_target_chars"])),
            "hard_max": int(cv_format_profile.get("bullet_length_hard_max", BULLET_POLICY["hard_max_chars"])),
        }

    def _render_with_profile(
        self,
        cv_format_profile: dict[str, Any],
        output_docx_path: str | None = None,
    ) -> dict[str, Any]:
        completed = subprocess.run(
            [
                sys.executable,
                str(ROOT_DIR / "render_cv.py"),
                "--template-path",
                str(cv_format_profile["template_path"]),
                "--template-map-path",
                str(cv_format_profile["template_map_path"]),
                "--insert-page-break-before-technical-projects",
                "true" if cv_format_profile["insert_page_break_before_technical_projects"] else "false",
                *(
                    ["--output-path", output_docx_path]
                    if output_docx_path
                    else []
                ),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            raise StageBlockedError(f"render_cv failed: {completed.stderr.strip()}")
        docx_path = completed.stdout.strip().splitlines()[-1].strip()
        pdf_path = str(convert_docx_to_pdf(docx_path))
        return {
            "docx_path": docx_path,
            "pdf_path": pdf_path,
            "template_path": cv_format_profile["template_path"],
            "template_map_path": cv_format_profile["template_map_path"],
            "expected_pages": cv_format_profile["expected_pages"],
        }

    def _reconcile_and_validate(
        self,
        selections: dict[str, Any],
        slot_plan: dict[str, Any],
        work_exp: dict[str, Any],
        cv_format_profile: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        raw_keywords = self.ckpt["artifacts"].get("jd_keywords") or _load_json(self.args.keywords_path, {})
        reconciled_slot_plan, reconcile_report = reconcile_slot_plan_targets(
            slot_plan=slot_plan,
            selections=selections,
            raw_keywords=raw_keywords,
        )
        if reconcile_report.get("changed"):
            _write_json(ARTIFACT_DEFAULT_PATHS["slot_plan"], reconciled_slot_plan)
            self.ckpt.setdefault("artifacts", {})["slot_plan"] = reconciled_slot_plan

        report = validate_cv_output(
            selections=selections,
            slot_plan=reconciled_slot_plan,
            work_exp=work_exp,
            length_limits=self._length_limits(cv_format_profile),
        )
        return report, reconciled_slot_plan, reconcile_report

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
        if start_idx > 0:
            meta = _load_json(self.args.meta_path, default={}) if self.args.meta_path.exists() else None
            self._ensure_cv_format_profile(meta=meta if isinstance(meta, dict) else None)
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
        cv_variant_id = self._ensure_cv_variant_id(meta)
        cv_format_profile = self._ensure_cv_format_profile(meta=meta)
        return {"job_meta": meta, "cv_format_profile": cv_format_profile, "cv_variant_id": cv_variant_id}

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
        cv_format_profile = self.ckpt["artifacts"].get("cv_format_profile") or self._ensure_cv_format_profile()
        template_map_path = Path(cv_format_profile["template_map_path"])
        template_map = _load_json(template_map_path, default={})
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
        cv_format_profile = self.ckpt["artifacts"].get("cv_format_profile") or self._ensure_cv_format_profile()
        template_map_path = Path(cv_format_profile["template_map_path"])
        template_map = _load_json(template_map_path, default={})
        job_meta = self.ckpt["artifacts"].get("job_meta", {})
        cv_variant_id = str(job_meta.get("cv_variant_id", self.ckpt["artifacts"].get("cv_variant_id", "")))
        previous = self.ckpt["artifacts"].get("slot_plan")
        plan = build_slot_plan(
            evidence=evidence,
            template_map=template_map,
            cv_variant_id=cv_variant_id,
        )
        _write_json(ARTIFACT_DEFAULT_PATHS["slot_plan"], plan)
        if previous and previous != plan:
            self.ckpt.setdefault("invalidations", []).extend(stages_to_invalidate("slot_plan"))
        if not plan.get("is_sufficient", False):
            raise StageBlockedError(
                "slot_plan is insufficient; ask insufficiency_questions, update cache, then resume from evidence_select"
            )
        return {"slot_plan": plan}

    def stage_coverage_plan(self) -> dict[str, Any]:
        slot_plan = self.ckpt["artifacts"].get("slot_plan") or _load_json(ARTIFACT_DEFAULT_PATHS["slot_plan"])
        if not slot_plan:
            raise StageBlockedError(f"Missing slot plan: {ARTIFACT_DEFAULT_PATHS['slot_plan']}")
        jd_keywords = self.ckpt["artifacts"].get("jd_keywords") or _load_json(self.args.keywords_path, {})
        cv_format_profile = self._current_cv_profile()
        explicit_ratio = float(cv_format_profile.get("explicit_coverage_ratio", BULLET_POLICY["explicit_coverage_ratio"]))
        job_meta = self.ckpt["artifacts"].get("job_meta", {})
        cv_variant_id = str(job_meta.get("cv_variant_id", self.ckpt["artifacts"].get("cv_variant_id", "")))

        previous = self.ckpt["artifacts"].get("coverage_plan")
        updated_slot_plan, coverage_report = build_coverage_plan(
            slot_plan=slot_plan,
            jd_keywords=jd_keywords,
            explicit_ratio=explicit_ratio,
            cv_variant_id=cv_variant_id,
        )
        _write_json(ARTIFACT_DEFAULT_PATHS["slot_plan"], updated_slot_plan)
        _write_json(ARTIFACT_DEFAULT_PATHS["coverage_plan"], coverage_report)
        if previous and previous != coverage_report:
            self.ckpt.setdefault("invalidations", []).extend(stages_to_invalidate("coverage_plan"))
        return {
            "slot_plan": updated_slot_plan,
            "coverage_plan": coverage_report,
            "coverage_report": coverage_report,
        }

    def stage_coverage_review(self) -> dict[str, Any]:
        coverage_report = self.ckpt["artifacts"].get("coverage_report") or _load_json(
            ARTIFACT_DEFAULT_PATHS["coverage_plan"],
            default={},
        )
        if not coverage_report:
            raise StageBlockedError("coverage_report missing; run coverage_plan first")

        uncovered_required = list(coverage_report.get("uncovered_required", []))
        uncovered_nice = list(coverage_report.get("uncovered_nice_to_have", []))
        if not (uncovered_required or uncovered_nice):
            return {"coverage_review": {"status": "not_required"}}

        review_path = self.args.coverage_review_path
        if not review_path.exists():
            review_path.parent.mkdir(parents=True, exist_ok=True)
            template = {
                "status": "pending",
                "notes": "",
                "uncovered_required": uncovered_required,
                "uncovered_nice_to_have": uncovered_nice,
                "uncovered_support": coverage_report.get("uncovered_support", {}),
            }
            _write_json(review_path, template)
            raise StageBlockedError(
                "coverage_review required. Create review file at "
                f"{review_path} with {{\"status\":\"approved\",\"notes\":\"...\"}} after reviewing uncovered terms "
                f"(required={uncovered_required}, nice_to_have={uncovered_nice})"
            )
        review = _load_json(review_path, default={})
        status = str(review.get("status", "")).strip().lower()
        if status != "approved":
            raise StageBlockedError(
                f"coverage_review file must set status=approved before drafting: {review_path}"
            )
        cache_updates = review.get("cache_updates", {})
        if isinstance(cache_updates, dict) and cache_updates and not review.get("cache_updates_applied", False):
            cache = _load_json(self.args.cache_path, default={})
            job_meta = self.ckpt["artifacts"].get("job_meta", {})
            for question_id, answer in cache_updates.items():
                text = str(answer or "").strip()
                if not text:
                    continue
                cache[str(question_id)] = {
                    "answer": text,
                    "job_id": job_meta.get("job_id"),
                    "ts": _utcnow(),
                    "source": "coverage_review",
                }
            _write_json(self.args.cache_path, cache)
            review["cache_updates_applied"] = True
            _write_json(review_path, review)
            raise StageBlockedError(
                "coverage_review cache_updates were applied. Re-run from stage evidence_select "
                "to refresh evidence, slot_plan, and coverage_plan before drafting."
            )
        return {"coverage_review": {"status": "approved", "path": str(review_path), "review": review}}

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
        if not selections:
            raise StageBlockedError(f"Missing draft selections: {self.args.selections_path}")
        slot_plan = self.ckpt["artifacts"].get("slot_plan") or _load_json(ARTIFACT_DEFAULT_PATHS["slot_plan"])
        if not slot_plan:
            raise StageBlockedError(f"Missing slot plan: {ARTIFACT_DEFAULT_PATHS['slot_plan']}")
        work_exp = _load_json(self.args.work_exp_path, default={})
        cv_format_profile = self._current_cv_profile()
        report, reconciled_slot_plan, reconcile_report = self._reconcile_and_validate(
            selections=selections,
            slot_plan=slot_plan,
            work_exp=work_exp,
            cv_format_profile=cv_format_profile,
        )
        if not report.get("ok", False):
            raise StageBlockedError("Deterministic validation failed; fix failed bullets and resume")
        return {
            "validated_bullets": report,
            "slot_plan": reconciled_slot_plan,
            "slot_plan_reconcile_report": reconcile_report,
        }

    def stage_render_docx_pdf(self) -> dict[str, Any]:
        docx_path = self.args.docx_path
        pdf_path = self.args.pdf_path
        cv_format_profile = self._current_cv_profile()
        if not docx_path:
            outputs = self._render_with_profile(cv_format_profile=cv_format_profile)
            docx_path = outputs["docx_path"]
            pdf_path = outputs["pdf_path"]
        if not pdf_path:
            pdf_path = str(convert_docx_to_pdf(docx_path))

        outputs = {
            "docx_path": docx_path,
            "pdf_path": pdf_path,
            "template_path": cv_format_profile["template_path"],
            "template_map_path": cv_format_profile["template_map_path"],
            "expected_pages": cv_format_profile["expected_pages"],
        }
        return {"render_outputs": outputs}

    def stage_layout_gate_2pages(self) -> dict[str, Any]:
        render_outputs = self.ckpt["artifacts"].get("render_outputs")
        if not render_outputs:
            raise StageBlockedError("render_outputs missing; run render_docx_pdf first")
        cv_format_profile = self._current_cv_profile()
        expected_pages = int(cv_format_profile["expected_pages"])
        wrap_retry_budget = int(cv_format_profile.get("wrap_retry_budget", BULLET_POLICY["wrap_retry_budget"]))
        preferred_target = int(
            cv_format_profile.get("bullet_length_target", BULLET_POLICY["preferred_target_chars"])
        )

        attempt_reports: list[dict[str, Any]] = []
        final_pages = -1
        final_wrap_count = -1

        for attempt in range(0, wrap_retry_budget + 1):
            current_outputs = self.ckpt["artifacts"].get("render_outputs", render_outputs)
            pdf_path = Path(current_outputs["pdf_path"])
            selections = _load_json(self.args.selections_path, default={})

            pages = get_page_count(pdf_path)
            wrap_report = detect_wrapped_bullets(pdf_path=pdf_path, selections=selections)
            wrapped_bullets = list(wrap_report.get("wrapped_bullets", []))
            final_pages = pages
            final_wrap_count = len(wrapped_bullets)

            attempt_payload: dict[str, Any] = {
                "attempt": attempt,
                "pdf_path": str(pdf_path),
                "actual_pages": pages,
                "expected_pages": expected_pages,
                "wrapped_count": len(wrapped_bullets),
                "wrap_report": wrap_report,
            }
            attempt_reports.append(attempt_payload)

            if pages == expected_pages and not wrapped_bullets:
                report = {
                    "pdf_path": str(pdf_path),
                    "expected_pages": expected_pages,
                    "actual_pages": pages,
                    "page_match": True,
                    "wrapped_count": 0,
                    "iterations": attempt,
                    "attempts": attempt_reports,
                }
                self.ckpt["layout_report"] = report
                self.ckpt.setdefault("artifacts", {})["wrap_report"] = report
                return {"layout_report": report, "wrap_report": report}

            if attempt >= wrap_retry_budget:
                break
            if not wrapped_bullets:
                # Cannot auto-heal page mismatch if no specific wrapped bullets were detected.
                break

            slot_plan = self.ckpt["artifacts"].get("slot_plan") or _load_json(
                ARTIFACT_DEFAULT_PATHS["slot_plan"],
                default={},
            )
            rewritten, rephrase_report = rephrase_wrapped_bullets(
                selections=selections,
                slot_plan=slot_plan,
                wrapped_bullets=wrapped_bullets,
                preferred_target_chars=preferred_target,
            )
            attempt_payload["rephrase_report"] = rephrase_report
            if not rephrase_report.get("changed"):
                break

            _write_json(self.args.selections_path, rewritten)
            work_exp = _load_json(self.args.work_exp_path, default={})
            validation_report, reconciled_slot_plan, reconcile_report = self._reconcile_and_validate(
                selections=rewritten,
                slot_plan=slot_plan,
                work_exp=work_exp,
                cv_format_profile=cv_format_profile,
            )
            attempt_payload["validate_after_rephrase"] = validation_report
            attempt_payload["slot_plan_reconcile_report"] = reconcile_report
            if not validation_report.get("ok", False):
                raise StageBlockedError("Wrap rephrase pass caused validation failures; manual bullet fix required")

            self.ckpt.setdefault("artifacts", {})["slot_plan"] = reconciled_slot_plan
            rerendered = self._render_with_profile(
                cv_format_profile=cv_format_profile,
                output_docx_path=current_outputs.get("docx_path"),
            )
            self.ckpt.setdefault("artifacts", {})["render_outputs"] = rerendered
            render_outputs = rerendered

        raise StageBlockedError(
            "Layout gate failed after wrap optimization: "
            f"expected_pages={expected_pages}, actual_pages={final_pages}, wrapped_bullets={final_wrap_count}"
        )

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
        _append_jsonl(DEFAULT_FACT_PATCH_LOG, patch)
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
        handoff_path = REPO_ROOT / ".cv-apply-cover-letter-handoff.json"
        _write_json(handoff_path, handoff)
        return {"cover_letter_handoff": {"path": str(handoff_path)}}


def parse_args() -> RunnerArgs:
    parser = argparse.ArgumentParser(
        description="Checkpointed stage runner for /cv-apply",
        allow_abbrev=False,
    )
    parser.add_argument("--checkpoint", default=str(DEFAULT_CHECKPOINT_PATH))
    parser.add_argument("--metrics-log", default=str(DEFAULT_METRICS_LOG))
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--target-stage")
    parser.add_argument("--meta-path", default=str(ARTIFACT_DEFAULT_PATHS["meta"]))
    parser.add_argument("--keywords-path", default=str(ARTIFACT_DEFAULT_PATHS["jd_keywords"]))
    parser.add_argument("--work-exp-path", default=str(CANONICAL_FACT_STORES["work_experience"]))
    parser.add_argument("--store-path", default=str(CANONICAL_FACT_STORES["projects"]))
    parser.add_argument("--cache-path", default=str(CANONICAL_FACT_STORES["experience_cache"]))
    parser.add_argument("--project-selections-path", default=str(ARTIFACT_DEFAULT_PATHS["project_selections"]))
    parser.add_argument("--coverage-review-path", default=str(ARTIFACT_DEFAULT_PATHS["coverage_review"]))
    parser.add_argument("--cv-length-pages", type=int, choices=[1, 2])
    parser.add_argument("--template-path")
    parser.add_argument("--template-map-path")
    parser.add_argument("--expected-pages", type=int)
    parser.add_argument(
        "--insert-page-break-before-technical-projects",
        choices=["true", "false"],
    )
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
        coverage_review_path=Path(ns.coverage_review_path),
        cv_length_pages=ns.cv_length_pages,
        template_path=Path(ns.template_path) if ns.template_path else None,
        template_map_path=Path(ns.template_map_path) if ns.template_map_path else None,
        expected_pages=ns.expected_pages,
        insert_page_break_before_technical_projects=(
            None
            if ns.insert_page_break_before_technical_projects is None
            else ns.insert_page_break_before_technical_projects == "true"
        ),
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
