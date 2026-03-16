"""Persist CV generation outputs to the database.

Contract:
- Update job_status to cv_generated.
- Persist CV DOCX/PDF paths without modifying cover_letter_path.
- Prefer cv_docx_path/cv_pdf_path columns when present; fallback to cv_path.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psycopg2
from dotenv import load_dotenv


def _utcnow():
    return datetime.now(timezone.utc)


def _load_meta(meta_path: Path) -> dict[str, Any]:
    return json.loads(meta_path.read_text(encoding="utf-8-sig"))


def _column_exists(cur, table: str, column: str) -> bool:
    cur.execute(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = %s
          AND column_name = %s
        LIMIT 1
        """,
        (table, column),
    )
    return cur.fetchone() is not None


def persist_cv_paths(meta: dict[str, Any], docx_path: str, pdf_path: str) -> dict[str, Any]:
    load_dotenv(Path(r"C:/Code/CV_crawl") / ".env")
    db_url = os.environ["DATABASE_URL"]
    job_id = meta["job_id"]

    conn = psycopg2.connect(db_url)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE job_status SET status = 'cv_generated', status_updated = %s WHERE job_id = %s",
                (_utcnow(), job_id),
            )

            has_cv_docx = _column_exists(cur, "application_packs", "cv_docx_path")
            has_cv_pdf = _column_exists(cur, "application_packs", "cv_pdf_path")
            has_cv_path = _column_exists(cur, "application_packs", "cv_path")

            cur.execute("SELECT id FROM application_packs WHERE job_id = %s", (job_id,))
            row = cur.fetchone()
            if row:
                set_fragments = []
                values: list[Any] = []
                if has_cv_docx:
                    set_fragments.append("cv_docx_path = %s")
                    values.append(docx_path)
                if has_cv_pdf:
                    set_fragments.append("cv_pdf_path = %s")
                    values.append(pdf_path)
                if not set_fragments and has_cv_path:
                    set_fragments.append("cv_path = %s")
                    values.append(docx_path)
                if not set_fragments:
                    raise RuntimeError("application_packs has no supported CV columns")
                values.append(job_id)
                cur.execute(f"UPDATE application_packs SET {', '.join(set_fragments)} WHERE job_id = %s", tuple(values))
            else:
                insert_cols = ["job_id", "created_at"]
                insert_vals: list[Any] = [job_id, _utcnow()]
                if has_cv_docx:
                    insert_cols.append("cv_docx_path")
                    insert_vals.append(docx_path)
                if has_cv_pdf:
                    insert_cols.append("cv_pdf_path")
                    insert_vals.append(pdf_path)
                if not has_cv_docx and not has_cv_pdf and has_cv_path:
                    insert_cols.append("cv_path")
                    insert_vals.append(docx_path)
                placeholders = ", ".join(["%s"] * len(insert_cols))
                cur.execute(
                    f"INSERT INTO application_packs ({', '.join(insert_cols)}) VALUES ({placeholders})",
                    tuple(insert_vals),
                )

        conn.commit()
    finally:
        conn.close()

    return {
        "ok": True,
        "job_id": job_id,
        "docx_path": docx_path,
        "pdf_path": pdf_path,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Persist CV paths to DB without touching cover letter fields")
    parser.add_argument("pos_docx", nargs="?")
    parser.add_argument("pos_pdf", nargs="?")
    parser.add_argument("--meta", default=r"C:/Code/CV_crawl/.cv-apply-meta-tmp.json")
    parser.add_argument("--docx", dest="opt_docx")
    parser.add_argument("--pdf", dest="opt_pdf")
    args = parser.parse_args()

    # Backward compatibility: prefer positional args when both are supplied.
    if args.pos_docx and args.pos_pdf:
        docx_path = args.pos_docx
        pdf_path = args.pos_pdf
    else:
        docx_path = args.opt_docx or args.pos_docx
        pdf_path = args.opt_pdf or args.pos_pdf

    if not docx_path or not pdf_path:
        raise SystemExit("Provide DOCX and PDF paths via positional args or --docx/--pdf")

    meta = _load_meta(Path(args.meta))
    result = persist_cv_paths(meta=meta, docx_path=docx_path, pdf_path=pdf_path)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
