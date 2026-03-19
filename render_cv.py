"""Render CV DOCX from template + selections."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path

from agent.cv_renderer import render_cv
from agent.validators import UserSelections


DEFAULT_META_PATH = Path(r"C:\Code\CV_crawl\.cv-apply-meta-tmp.json")
DEFAULT_SELECTIONS_PATH = Path(r"C:\Code\CV_crawl\.cv-apply-selections-tmp.json")
DEFAULT_TEMPLATE_PATH = Path(r"C:\Code\CV_crawl\profile\cv_template.docx")
DEFAULT_TEMPLATE_MAP_PATH = Path(r"C:\Code\CV_crawl\profile\template_map.json")
DEFAULT_OUTPUT_DIR = Path(
    r"C:\Users\brans\OneDrive - University of Leeds\GraduateJobHunting\claude-cv-outputs"
)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _default_output_path(meta: dict) -> Path:
    safe_company = re.sub(r"[^\w\-]", "_", str(meta["company"]))
    safe_role = re.sub(r"[^\w\-]", "_", str(meta["job_title"]))[:30]
    stamp = datetime.now().strftime("%Y%m%d")
    return DEFAULT_OUTPUT_DIR / f"{safe_company}_{safe_role}_{stamp}.docx"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render CV DOCX from selections JSON",
        allow_abbrev=False,
    )
    parser.add_argument("--meta-path", default=str(DEFAULT_META_PATH))
    parser.add_argument("--selections-path", default=str(DEFAULT_SELECTIONS_PATH))
    parser.add_argument("--template-path", default=str(DEFAULT_TEMPLATE_PATH))
    parser.add_argument("--template-map-path", default=str(DEFAULT_TEMPLATE_MAP_PATH))
    parser.add_argument(
        "--insert-page-break-before-technical-projects",
        choices=["true", "false"],
        default="true",
    )
    parser.add_argument("--output-path")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    meta_path = Path(args.meta_path)
    selections_path = Path(args.selections_path)
    template_path = Path(args.template_path)
    template_map_path = Path(args.template_map_path)
    insert_page_break = args.insert_page_break_before_technical_projects == "true"

    meta = _load_json(meta_path)
    sdata = _load_json(selections_path)
    selections = UserSelections(**sdata)

    out_path = Path(args.output_path) if args.output_path else _default_output_path(meta)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    render_cv(
        template_path=template_path,
        template_map_path=template_map_path,
        selections=selections,
        job={"job_id": meta["job_id"], "title": meta["job_title"], "company": meta["company"]},
        output_path=out_path,
        insert_page_break_before_technical_projects=insert_page_break,
    )
    print(str(out_path))


if __name__ == "__main__":
    main()
