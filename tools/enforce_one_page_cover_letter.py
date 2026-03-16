"""Render and enforce one-page cover letter output.

This script renders DOCX, converts to PDF, and checks page count.
If output exceeds one page, it retries with tighter layout presets.

Usage:
    python tools/enforce_one_page_cover_letter.py <input.json>

Prints a JSON object to stdout on success:
    {"docx_path": "...", "pdf_path": "...", "pages": 1, "layout_preset": "tight"}
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from render_cover_letter import render
from docx_to_pdf import convert as convert_docx_to_pdf
from check_pdf_pages import get_page_count


LAYOUT_SEQUENCE = ["default", "tight", "tighter"]


def _load_payload(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"JSON file not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _render_and_count(data: dict, preset: str) -> tuple[Path, Path, int]:
    payload = dict(data)
    payload["layout_preset"] = preset

    docx_path = render(payload)
    pdf_path = convert_docx_to_pdf(docx_path)
    page_count = get_page_count(pdf_path)
    return docx_path, pdf_path, page_count


def main() -> None:
    if len(sys.argv) < 2:
        print(f"Usage: python {sys.argv[0]} <input.json>", file=sys.stderr)
        sys.exit(1)

    json_path = Path(sys.argv[1])
    base_data = _load_payload(json_path)

    last_docx_path: Path | None = None
    last_pdf_path: Path | None = None
    last_page_count: int | None = None

    for preset in LAYOUT_SEQUENCE:
        docx_path, pdf_path, page_count = _render_and_count(base_data, preset)
        last_docx_path = docx_path
        last_pdf_path = pdf_path
        last_page_count = page_count

        if page_count == 1:
            print(
                json.dumps(
                    {
                        "docx_path": str(docx_path),
                        "pdf_path": str(pdf_path),
                        "pages": page_count,
                        "layout_preset": preset,
                    }
                )
            )
            return

    print(
        json.dumps(
            {
                "docx_path": str(last_docx_path) if last_docx_path else "",
                "pdf_path": str(last_pdf_path) if last_pdf_path else "",
                "pages": last_page_count,
                "layout_preset": "failed",
                "error": "Could not fit into one page with available layout presets",
            }
        ),
        file=sys.stderr,
    )
    sys.exit(2)


if __name__ == "__main__":
    main()
