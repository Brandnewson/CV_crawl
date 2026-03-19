"""Refresh discovery status for safe reruns.

Resets rejected jobs and recently cv-generated jobs back to `new` and clears scoring
fields so discovery/scoring can reprocess them.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import psycopg2
from dotenv import load_dotenv


DEFAULT_PROJECT_ROOT = Path(r"C:\Code\CV_crawl")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Refresh discovery state before rerun",
        allow_abbrev=False,
    )
    parser.add_argument(
        "--reopen-cv-generated-days",
        type=int,
        default=7,
        help="Reopen cv_generated rows updated within this many days",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview counts without applying updates",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    load_dotenv(DEFAULT_PROJECT_ROOT / ".env")
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise SystemExit("DATABASE_URL not found in environment")

    conn = psycopg2.connect(db_url)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*)
                FROM job_status
                WHERE status = 'rejected'
                """
            )
            rejected_count = int(cur.fetchone()[0])

            cur.execute(
                """
                SELECT COUNT(*)
                FROM job_status
                WHERE status = 'cv_generated'
                  AND status_updated >= NOW() - (%s || ' days')::INTERVAL
                """,
                (args.reopen_cv_generated_days,),
            )
            recent_cv_generated_count = int(cur.fetchone()[0])

            if args.dry_run:
                payload = {
                    "dry_run": True,
                    "reopen_cv_generated_days": args.reopen_cv_generated_days,
                    "rejected_rows_to_reopen": rejected_count,
                    "cv_generated_rows_to_reopen": recent_cv_generated_count,
                    "total_rows_to_reopen": rejected_count + recent_cv_generated_count,
                }
                print(json.dumps(payload, ensure_ascii=False))
                conn.rollback()
                return

            cur.execute(
                """
                UPDATE job_status
                SET status = 'new',
                    fit_score = NULL,
                    fit_summary = NULL,
                    keyword_matches = NULL,
                    status_updated = NOW()
                WHERE status = 'rejected'
                """
            )
            rejected_reopened = int(cur.rowcount)

            cur.execute(
                """
                UPDATE job_status
                SET status = 'new',
                    fit_score = NULL,
                    fit_summary = NULL,
                    keyword_matches = NULL,
                    status_updated = NOW()
                WHERE status = 'cv_generated'
                  AND status_updated >= NOW() - (%s || ' days')::INTERVAL
                """,
                (args.reopen_cv_generated_days,),
            )
            cv_generated_reopened = int(cur.rowcount)

        conn.commit()
    finally:
        conn.close()

    payload = {
        "ok": True,
        "reopen_cv_generated_days": args.reopen_cv_generated_days,
        "rejected_rows_reopened": rejected_reopened,
        "cv_generated_rows_reopened": cv_generated_reopened,
        "total_rows_reopened": rejected_reopened + cv_generated_reopened,
    }
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
