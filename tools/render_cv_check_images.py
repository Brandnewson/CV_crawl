"""Render DOCX to PDF check images and return page metadata."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import comtypes.client
import fitz


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="DOCX -> PDF -> page images for visual checks", allow_abbrev=False)
    parser.add_argument("--docx-path", required=True, help="Input DOCX path")
    parser.add_argument("--output-dir", default=str(Path.cwd()), help="Directory for output images")
    parser.add_argument("--dpi", type=int, default=150)
    parser.add_argument("--pdf-path", help="Optional explicit check PDF path")
    parser.add_argument("--cleanup-pdf", action="store_true", help="Delete generated PDF after image export")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    docx_path = Path(args.docx_path)
    if not docx_path.exists():
        raise FileNotFoundError(f"DOCX not found: {docx_path}")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = Path(args.pdf_path) if args.pdf_path else docx_path.with_name(f"{docx_path.stem}_check.pdf")

    word = comtypes.client.CreateObject("Word.Application")
    word.Visible = False

    image_paths: list[str] = []
    try:
        doc = word.Documents.Open(os.path.abspath(str(docx_path)))
        doc.SaveAs(os.path.abspath(str(pdf_path)), FileFormat=17)
        doc.Close()
    finally:
        word.Quit()

    pdf = fitz.open(str(pdf_path))
    page_count = pdf.page_count
    try:
        matrix = fitz.Matrix(args.dpi / 72, args.dpi / 72)
        for i, page in enumerate(pdf):
            image_path = output_dir / f"cv_check_page_{i + 1}.jpg"
            pix = page.get_pixmap(matrix=matrix)
            pix.save(str(image_path))
            image_paths.append(str(image_path))
    finally:
        pdf.close()

    if args.cleanup_pdf:
        try:
            pdf_path.unlink()
        except OSError:
            pass

    print(
        json.dumps(
            {
                "docx_path": str(docx_path),
                "pdf_path": str(pdf_path),
                "page_count": page_count,
                "image_paths": image_paths,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
