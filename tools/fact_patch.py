"""Feedback classifier and safe fact patch helpers for /cv-apply."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from cv_apply_contract import DEFAULT_FACT_PATCH_LOG


FEEDBACK_TYPES = ("factual_correction", "missing_fact", "overstated_scope", "style_priority")


def classify_feedback(feedback_text: str) -> str:
    text = feedback_text.lower()
    if any(term in text for term in ("wrong", "incorrect", "not true", "didn't", "did not", "never")):
        return "factual_correction"
    if any(term in text for term in ("missing", "add", "forgot", "also did", "include")):
        return "missing_fact"
    if any(term in text for term in ("overstate", "too strong", "tone down", "not sole", "partial")):
        return "overstated_scope"
    return "style_priority"


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def append_patch_log(entry: dict[str, Any], path: Path = DEFAULT_FACT_PATCH_LOG) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def apply_patch_if_safe(
    patch: dict[str, Any],
    work_exp_path: Path,
    project_store_path: Path,
) -> tuple[bool, str]:
    target_store = patch.get("target_store")
    target_record_id = patch.get("target_record_id", "")
    after = patch.get("after", "")
    conflict_check = {"ok": True, "reason": ""}

    if target_store == "work_experience":
        data = _load(work_exp_path)
        try:
            _, org_slug, idx_str = target_record_id.split(":", 2)
            fact_index = int(idx_str)
        except Exception:
            return False, "Invalid target_record_id for work_experience"

        for role in data.get("work_experience", []):
            if role.get("org", "").lower().replace(" ", "_") == org_slug:
                not_terms = [str(v).lower() for v in role.get("explicit_not", [])]
                after_lower = str(after).lower()
                for term in not_terms:
                    if term and term in after_lower:
                        conflict_check = {"ok": False, "reason": f"explicit_not conflict: {term}"}
                        break
                if not conflict_check["ok"]:
                    patch["conflict_check"] = conflict_check
                    return False, conflict_check["reason"]
                facts = role.get("verified_facts", [])
                if fact_index >= len(facts):
                    return False, "fact_index out of bounds"
                before = facts[fact_index]
                facts[fact_index] = after
                _write(work_exp_path, data)
                patch["before"] = before
                patch["conflict_check"] = conflict_check
                return True, "applied"
        return False, "target role not found"

    if target_store == "projects":
        data = _load(project_store_path)
        try:
            _, project_slug, idx_str = target_record_id.split(":", 2)
            bullet_index = int(idx_str)
        except Exception:
            return False, "Invalid target_record_id for projects"
        for project in data.get("projects", []):
            if project.get("name", "").lower().replace(" ", "_") == project_slug:
                bullets = project.get("bullets", [])
                if bullet_index >= len(bullets):
                    return False, "bullet index out of bounds"
                before = bullets[bullet_index].get("text", "")
                bullets[bullet_index]["text"] = after
                _write(project_store_path, data)
                patch["before"] = before
                patch["conflict_check"] = conflict_check
                return True, "applied"
        return False, "target project not found"

    return False, f"Unsupported target_store: {target_store}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Classify feedback and apply safe fact patches")
    parser.add_argument("--mode", choices=("classify", "apply"), required=True)
    parser.add_argument("--feedback", help="Feedback text")
    parser.add_argument("--patch-json", help="Patch json path for apply mode")
    from cv_apply_contract import CANONICAL_FACT_STORES
    parser.add_argument("--work-exp", default=str(CANONICAL_FACT_STORES["work_experience"]))
    parser.add_argument("--projects", default=str(CANONICAL_FACT_STORES["projects"]))
    args = parser.parse_args()

    if args.mode == "classify":
        if not args.feedback:
            raise SystemExit("--feedback is required for classify mode")
        print(json.dumps({"feedback_type": classify_feedback(args.feedback)}))
        return

    if not args.patch_json:
        raise SystemExit("--patch-json is required for apply mode")
    patch_path = Path(args.patch_json)
    patch = _load(patch_path)
    ok, msg = apply_patch_if_safe(
        patch=patch,
        work_exp_path=Path(args.work_exp),
        project_store_path=Path(args.projects),
    )
    patch["applied"] = ok
    if not ok:
        patch["conflict_check"]["ok"] = False
        if not patch["conflict_check"].get("reason"):
            patch["conflict_check"]["reason"] = msg
    patch_path.write_text(json.dumps(patch, indent=2, ensure_ascii=False), encoding="utf-8")
    append_patch_log(patch)
    print(json.dumps({"ok": ok, "message": msg}))


if __name__ == "__main__":
    main()
