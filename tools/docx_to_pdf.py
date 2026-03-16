"""Convert DOCX to PDF using docx2pdf (Word COM on Windows).

Usage:
    python tools/docx_to_pdf.py <input.docx> [output.pdf]

If output path is omitted, writes <input_stem>.pdf alongside the DOCX.
Requires Microsoft Word installed on Windows.
"""

import sys
from pathlib import Path


def convert(docx_path: str | Path, pdf_path: str | Path | None = None) -> Path:
    """Convert docx_path to PDF. Returns the PDF path."""
    from docx2pdf import convert as _convert

    docx_path = Path(docx_path)
    if not docx_path.exists():
        raise FileNotFoundError(f"DOCX not found: {docx_path}")

    if pdf_path is None:
        pdf_path = docx_path.with_suffix(".pdf")
    pdf_path = Path(pdf_path)

    _convert(str(docx_path), str(pdf_path))
    return pdf_path


def main() -> None:
    if len(sys.argv) < 2:
        print(f"Usage: python {sys.argv[0]} <input.docx> [output.pdf]", file=sys.stderr)
        sys.exit(1)

    docx_path = sys.argv[1]
    pdf_path = sys.argv[2] if len(sys.argv) > 2 else None

    out = convert(docx_path, pdf_path)
    print(f"PDF written to: {out}")


if __name__ == "__main__":
    main()
