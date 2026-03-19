"""Shared contracts for the checkpointed /cv-apply pipeline."""

from __future__ import annotations

import re
from pathlib import Path


CHECKPOINT_SCHEMA_VERSION = 1
DEFAULT_CHECKPOINT_PATH = Path(r"C:\Code\CV_crawl\.cv-apply-checkpoint.json")
DEFAULT_FACT_PATCH_LOG = Path(r"C:\Code\CV_crawl\.cv-fact-patches.jsonl")
DEFAULT_METRICS_LOG = Path(r"C:\Code\CV_crawl\.cv-apply-run-metrics.jsonl")

CV_FORMAT_PROFILES = {
    2: {
        "name": "2-page",
        "template_path": Path(r"C:\Code\CV_crawl\profile\cv_template.docx"),
        "template_map_path": Path(r"C:\Code\CV_crawl\profile\template_map.json"),
        "expected_pages": 2,
        "insert_page_break_before_technical_projects": True,
        "bullet_length_min": 80,
        "bullet_length_max": 115,
        "compact_length_max": 110,
    },
    1: {
        "name": "1-page",
        "template_path": Path(r"C:\Code\CV_crawl\reference_files\Branson Tay CV 1 page template.docx"),
        "template_map_path": Path(r"C:\Code\CV_crawl\profile\template_map_1page.json"),
        "expected_pages": 1,
        "insert_page_break_before_technical_projects": False,
        "bullet_length_min": 80,
        "bullet_length_max": 105,
        "compact_length_max": 100,
    },
}

CANONICAL_FACT_STORES = {
    "work_experience": Path(r"C:\Code\CV_crawl\.cv-work-experience.json"),
    "projects": Path(r"C:\Code\CV_crawl\.cv-harvest-store.json"),
    "experience_cache": Path(r"C:\Code\CV_crawl\.experience-cache.json"),
    "promoted_facts": Path(r"C:\Code\CV_crawl\.cv-facts-promoted.json"),
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
