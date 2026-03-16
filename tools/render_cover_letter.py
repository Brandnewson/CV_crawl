"""Render a cover letter to DOCX using python-docx.

Input JSON schema:
{
    "name":           "Branson Tay",
    "address_line1":  "14 Samara West Mount",
    "address_line2":  "59-61 Clarendon Road",
    "address_line3":  "Leeds, West Yorkshire LS2 9NZ",
    "email":          "bransontay@gmail.com",
    "company_name":   "McLaren Racing",
    "company_address": "Woking, United Kingdom",   # optional, may be empty
    "date":           "14th March 2026",
    "salutation":     "Dear Hiring Manager,",
    "intro":          "...",
    "para1":          "...",
    "para2":          "...",
    "para3":          "...",
    "conclusion":     "...",
    "company":        "McLaren_Racing",            # safe filename slug
    "role":           "Junior_Data_Engineer"       # safe filename slug (max 30 chars)
}

Usage:
    uv run --project "C:/Code/CV_CoverLetter_Generator_Agentic_Pipeline/job-pipeline" \\
        python "C:/Code/CV_crawl/tools/render_cover_letter.py" <json_path>

Writes DOCX to:
    C:\\Users\\brans\\OneDrive - University of Leeds\\GraduateJobHunting\\claude-cv-outputs\\
    {Company}_{Role}_CoverLetter_{YYYYMMDD}.docx

Prints the output path to stdout.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

OUTPUT_DIR = Path(
    r"C:\Users\brans\OneDrive - University of Leeds\GraduateJobHunting\claude-cv-outputs"
)


def _set_font(run, name: str, size_pt: float, bold: bool = False) -> None:
    from docx.shared import Pt
    run.font.name = name
    run.font.size = Pt(size_pt)
    run.font.bold = bold


def _add_paragraph(doc, text: str, font_name: str = "Garamond", font_size: float = 11,
                   space_before: float = 0, space_after: float = 6) -> None:
    """Add a paragraph with consistent formatting."""
    from docx.shared import Pt
    para = doc.add_paragraph()
    para.paragraph_format.space_before = Pt(space_before)
    para.paragraph_format.space_after = Pt(space_after)
    para.paragraph_format.line_spacing = 1.15
    run = para.add_run(text)
    _set_font(run, font_name, font_size)
    return para


def render(data: dict) -> Path:
    from docx import Document
    from docx.shared import Cm, Pt
    from docx.enum.text import WD_LINE_SPACING

    doc = Document()

    # ── Page margins: 2.5 cm all sides ──────────────────────────────────────
    for section in doc.sections:
        section.top_margin    = Cm(2.5)
        section.bottom_margin = Cm(2.5)
        section.left_margin   = Cm(2.5)
        section.right_margin  = Cm(2.5)

    # ── Helper: styled paragraph ─────────────────────────────────────────────
    def para(text: str, size: float = 11, bold: bool = False,
             space_before: float = 0, space_after: float = 5) -> None:
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(space_before)
        p.paragraph_format.space_after  = Pt(space_after)
        p.paragraph_format.line_spacing = 1.15
        r = p.add_run(text)
        r.font.name  = "Garamond"
        r.font.size  = Pt(size)
        r.font.bold  = bold

    # ── Sender name ──────────────────────────────────────────────────────────
    para(data.get("name", "Branson Tay"), size=12, bold=True, space_after=2)

    # ── Sender address lines ─────────────────────────────────────────────────
    for field in ("address_line1", "address_line2", "address_line3"):
        val = data.get(field, "")
        if val:
            para(val, space_after=2)

    email = data.get("email", "")
    if email:
        para(email, space_after=8)

    # ── Company name + address (optional) ───────────────────────────────────
    company_name = data.get("company_name", "")
    if company_name:
        para(company_name, space_after=2)

    company_address = data.get("company_address", "")
    if company_address:
        para(company_address, space_after=2)

    # ── Date ─────────────────────────────────────────────────────────────────
    para(data.get("date", datetime.today().strftime("%d %B %Y").lstrip("0")), space_after=10)

    # ── Salutation ───────────────────────────────────────────────────────────
    para(data.get("salutation", "Dear Hiring Manager,"), space_after=8)

    # ── Body paragraphs ──────────────────────────────────────────────────────
    for key in ("intro", "para1", "para2", "para3", "conclusion"):
        text = data.get(key, "")
        if text:
            para(text, space_before=0, space_after=8)

    # ── Sign-off ─────────────────────────────────────────────────────────────
    para("Yours Faithfully,", space_before=4, space_after=20)
    para(data.get("name", "Branson Tay"), size=11, bold=False, space_after=0)

    # ── Output path ──────────────────────────────────────────────────────────
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    safe_company = data.get("company", "Company")[:40]
    safe_role    = data.get("role", "Role")[:30]
    datestamp    = datetime.now().strftime("%Y%m%d")
    out_path     = OUTPUT_DIR / f"{safe_company}_{safe_role}_CoverLetter_{datestamp}.docx"

    doc.save(str(out_path))
    return out_path


def main() -> None:
    if len(sys.argv) < 2:
        print(f"Usage: python {sys.argv[0]} <json_path>", file=sys.stderr)
        sys.exit(1)

    json_path = Path(sys.argv[1])
    if not json_path.exists():
        print(f"ERROR: JSON file not found: {json_path}", file=sys.stderr)
        sys.exit(1)

    data = json.loads(json_path.read_text(encoding="utf-8"))
    out_path = render(data)
    print(str(out_path))


if __name__ == "__main__":
    main()
