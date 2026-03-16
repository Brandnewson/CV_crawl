"""Query PostgreSQL job DB and return ranked job list as JSON.

Usage (via uv):
    uv run --project "C:/Code/CV_CoverLetter_Generator_Agentic_Pipeline/job-pipeline" \
        python "C:/Code/CV_crawl/tools/query_jobs.py" [--min-score 0.65] [--status new] [--limit 20] [--include-recent]

Without --include-recent: returns JSON array of new jobs sorted by fit_score descending.
With --include-recent:    returns {"new_jobs": [...], "recent_jobs": [...]} where recent_jobs
                          are the 5 most recently CV-generated jobs ordered by generation date.

Exits non-zero on any failure — no fallbacks.
"""

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
import psycopg2

load_dotenv(Path(__file__).parent.parent / ".env")


def _serialise_dates(rows: list[dict], *cols: str) -> None:
    """Convert date/datetime columns to ISO strings in-place."""
    for row in rows:
        for col in cols:
            if row.get(col) and hasattr(row[col], "isoformat"):
                row[col] = row[col].isoformat()


def query_jobs(min_score: float = 0.65, status: str = "new", limit: int = 20) -> list[dict]:
    """Query jobs table and return ranked list. Raises on any failure."""
    db_url = os.environ.get("DATABASE_URL", "postgresql://localhost/jobpipeline")

    conn = psycopg2.connect(db_url)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    j.id,
                    j.title,
                    j.company,
                    j.location,
                    j.description,
                    j.job_url,
                    j.date_posted,
                    js.fit_score,
                    js.fit_summary,
                    js.status
                FROM jobs j
                JOIN job_status js ON js.job_id = j.id
                WHERE js.fit_score >= %s
                  AND js.status = %s
                ORDER BY js.fit_score DESC
                LIMIT %s
                """,
                (min_score, status, limit),
            )
            cols = [d[0] for d in cur.description]
            rows = [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        conn.close()

    _serialise_dates(rows, "date_posted")
    return rows


def query_recent_jobs(limit: int = 5) -> list[dict]:
    """Return the N most recently CV-generated jobs, ordered by generation date DESC."""
    db_url = os.environ.get("DATABASE_URL", "postgresql://localhost/jobpipeline")

    conn = psycopg2.connect(db_url)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    j.id,
                    j.title,
                    j.company,
                    j.location,
                    j.description,
                    j.job_url,
                    j.date_posted,
                    js.fit_score,
                    js.fit_summary,
                    js.status,
                    ap.created_at AS cv_generated_at
                FROM application_packs ap
                JOIN jobs j ON j.id = ap.job_id
                JOIN job_status js ON js.job_id = j.id
                ORDER BY ap.created_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            cols = [d[0] for d in cur.description]
            rows = [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        conn.close()

    _serialise_dates(rows, "date_posted", "cv_generated_at")
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Query ranked jobs from DB")
    parser.add_argument("--min-score", type=float, default=0.65)
    parser.add_argument("--status", default="new")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument(
        "--include-recent",
        action="store_true",
        help="Also return 5 most recently CV-generated jobs for rerun selection",
    )
    parser.add_argument("--recent-limit", type=int, default=5)
    args = parser.parse_args()

    if args.include_recent:
        output = {
            "new_jobs": query_jobs(args.min_score, args.status, args.limit),
            "recent_jobs": query_recent_jobs(args.recent_limit),
        }
    else:
        output = query_jobs(args.min_score, args.status, args.limit)

    sys.stdout.buffer.write(json.dumps(output, indent=2, ensure_ascii=False).encode("utf-8"))
    sys.stdout.buffer.write(b"\n")


if __name__ == "__main__":
    main()
