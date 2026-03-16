"""Shared contracts for the checkpointed /cv-apply pipeline."""

from __future__ import annotations

import re
from pathlib import Path


CHECKPOINT_SCHEMA_VERSION = 1
DEFAULT_CHECKPOINT_PATH = Path(r"C:\Code\CV_crawl\.cv-apply-checkpoint.json")
DEFAULT_FACT_PATCH_LOG = Path(r"C:\Code\CV_crawl\.cv-fact-patches.jsonl")
DEFAULT_METRICS_LOG = Path(r"C:\Code\CV_crawl\.cv-apply-run-metrics.jsonl")

CANONICAL_FACT_STORES = {
    "work_experience": Path(r"C:\Code\CV_crawl\.cv-work-experience.json"),
    "projects": Path(r"C:\Code\CV_crawl\.cv-harvest-store.json"),
    "experience_cache": Path(r"C:\Code\CV_crawl\.experience-cache.json"),
}

ARTIFACT_DEFAULT_PATHS = {
    "jd_keywords": Path(r"C:\Code\CV_crawl\.cv-apply-jd-keywords-tmp.json"),
    "project_selections": Path(r"C:\Code\CV_crawl\.cv-apply-project-selections.json"),
    "evidence_packs": Path(r"C:\Code\CV_crawl\.cv-apply-evidence-pack-tmp.json"),
    "slot_plan": Path(r"C:\Code\CV_crawl\.cv-apply-slot-plan-tmp.json"),
    "draft_sections": Path(r"C:\Code\CV_crawl\.cv-apply-selections-tmp.json"),
    "meta": Path(r"C:\Code\CV_crawl\.cv-apply-meta-tmp.json"),
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
    "slot_plan": {"draft_work_experience", "draft_technical_projects", "assemble", "validate_deterministic", "render_docx_pdf", "layout_gate_2pages"},
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
