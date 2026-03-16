"""Check page count for a PDF file.

Usage:
    python tools/check_pdf_pages.py <input.pdf> [expected_pages]

If expected_pages is provided, exits 0 only when page count matches.
Prints page count to stdout in both modes.
"""

from __future__ import annotations

import sys
from pathlib import Path


def get_page_count(pdf_path: str | Path) -> int:
    from pypdf import PdfReader

    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    reader = PdfReader(str(pdf_path))
    return len(reader.pages)


def main() -> None:
    if len(sys.argv) < 2:
        print(f"Usage: python {sys.argv[0]} <input.pdf> [expected_pages]", file=sys.stderr)
        sys.exit(1)

    pdf_path = Path(sys.argv[1])
    expected = int(sys.argv[2]) if len(sys.argv) >= 3 else None

    pages = get_page_count(pdf_path)
    print(pages)

    if expected is not None and pages != expected:
        sys.exit(2)


if __name__ == "__main__":
    main()
