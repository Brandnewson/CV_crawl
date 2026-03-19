"""Shared contracts for the checkpointed /cv-apply pipeline."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_user_config() -> dict:
    p = REPO_ROOT / "user_config.yaml"
    if p.exists():
        return yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return {}


_USER_CONFIG = _load_user_config()

DEFAULT_CV_OUTPUT_DIR = Path(
    _USER_CONFIG.get("cv_output_dir") or str(REPO_ROOT / "cv-outputs")
)
DEFAULT_TRACKER_PATH = Path(
    _USER_CONFIG.get("applications_tracker_path")
    or str(DEFAULT_CV_OUTPUT_DIR / "applications_tracker.xlsx")
)


def ensure_tmp_dir() -> None:
    (REPO_ROOT / ".tmp").mkdir(exist_ok=True)


ensure_tmp_dir()

CHECKPOINT_SCHEMA_VERSION = 2
DEFAULT_CHECKPOINT_PATH = REPO_ROOT / ".tmp" / ".cv-apply-checkpoint.json"
DEFAULT_FACT_PATCH_LOG = REPO_ROOT / ".cv-fact-patches.jsonl"
DEFAULT_METRICS_LOG = REPO_ROOT / ".cv-apply-run-metrics.jsonl"

BULLET_POLICY = {
    "hard_max_chars": 120,
    "preferred_target_chars": 110,
    "explicit_coverage_ratio": 0.5,
    "wrap_retry_budget": 3,
}

CV_FORMAT_PROFILES = {
    2: {
        "name": "2-page",
        "template_path": REPO_ROOT / "profile" / "cv_template.docx",
        "template_map_path": REPO_ROOT / "profile" / "template_map.json",
        "expected_pages": 2,
        "insert_page_break_before_technical_projects": True,
        "bullet_length_min": 80,
        "bullet_length_max": BULLET_POLICY["hard_max_chars"],
    },
    1: {
        "name": "1-page",
        "template_path": REPO_ROOT / "profile" / "cv_template_1page.docx",
        "template_map_path": REPO_ROOT / "profile" / "template_map_1page.json",
        "expected_pages": 1,
        "insert_page_break_before_technical_projects": False,
        "bullet_length_min": 80,
        "bullet_length_max": BULLET_POLICY["hard_max_chars"],
    },
}

CANONICAL_FACT_STORES = {
    "work_experience": REPO_ROOT / ".cv-work-experience.json",
    "projects": REPO_ROOT / ".cv-harvest-store.json",
    "experience_cache": REPO_ROOT / ".experience-cache.json",
    "promoted_facts": REPO_ROOT / ".cv-facts-promoted.json",
}

ARTIFACT_DEFAULT_PATHS = {
    "jd_keywords": REPO_ROOT / ".tmp" / ".cv-apply-jd-keywords-tmp.json",
    "project_selections": REPO_ROOT / ".tmp" / ".cv-apply-project-selections.json",
    "evidence_packs": REPO_ROOT / ".tmp" / ".cv-apply-evidence-pack-tmp.json",
    "slot_plan": REPO_ROOT / ".tmp" / ".cv-apply-slot-plan-tmp.json",
    "coverage_plan": REPO_ROOT / ".tmp" / ".cv-apply-coverage-plan-tmp.json",
    "coverage_review": REPO_ROOT / ".tmp" / ".cv-apply-coverage-review-tmp.json",
    "draft_sections": REPO_ROOT / ".tmp" / ".cv-apply-selections-tmp.json",
    "meta": REPO_ROOT / ".tmp" / ".cv-apply-meta-tmp.json",
}

STAGE_ORDER = [
    "job_select",
    "jd_extract",
    "source_load",
    "project_select",
    "gap_detect",
    "gap_normalize",
    "evidence_select",
    "slot_plan",
    "coverage_plan",
    "coverage_review",
    "draft_work_experience",
    "draft_technical_projects",
    "assemble",
    "validate_deterministic",
    "render_docx_pdf",
    "layout_gate_2pages",
    "preview_feedback",
    "feedback_classify",
    "fact_patch_apply",
    "targeted_regen",
    "persist_db",
    "cover_letter_handoff",
]

INVALIDATION_RULES = {
    "slot_plan": {
        "coverage_plan",
        "coverage_review",
        "draft_work_experience",
        "draft_technical_projects",
        "assemble",
        "validate_deterministic",
        "render_docx_pdf",
        "layout_gate_2pages",
    },
    "coverage_plan": {
        "coverage_review",
        "draft_work_experience",
        "draft_technical_projects",
        "assemble",
        "validate_deterministic",
        "render_docx_pdf",
        "layout_gate_2pages",
    },
    "fact_patch_apply": {"targeted_regen", "validate_deterministic", "render_docx_pdf", "layout_gate_2pages"},
    "feedback_classify_style": {"targeted_regen", "validate_deterministic", "render_docx_pdf", "layout_gate_2pages"},
}


def stage_index(stage_name: str) -> int:
    return STAGE_ORDER.index(stage_name)


def normalize_subsection_id(section: str, subsection: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", subsection.lower()).strip("_")
    return f"{section}:{slug}"


def stages_to_invalidate(trigger: str) -> list[str]:
    return sorted(INVALIDATION_RULES.get(trigger, set()), key=stage_index)


def normalise_keyword_target(value: str) -> str:
    """Normalise a keyword target for deterministic phrase matching."""
    text = re.sub(r"\s+", " ", str(value or "").strip().lower())
    text = text.strip(".,;:!?()[]{}\"'")
    if not text:
        return ""
    text = re.sub(r"\s*/\s*", " / ", text)
    return re.sub(r"\s+", " ", text).strip()


def target_in_text(target: str, text: str) -> bool:
    """Case-insensitive literal phrase check against normalised whitespace."""
    target_n = normalise_keyword_target(target)
    if not target_n:
        return True
    haystack = re.sub(r"\s+", " ", str(text or "").strip().lower())
    return target_n in haystack
