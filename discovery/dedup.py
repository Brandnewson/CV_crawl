"""Fuzzy deduplication module for cross-source job matching."""

from difflib import SequenceMatcher
from typing import Any

import psycopg2


def title_similarity(title1: str, title2: str) -> float:
    """
    Calculate string similarity between two job titles.

    Args:
        title1: First job title
        title2: Second job title

    Returns:
        Similarity score between 0.0 and 1.0
    """
    if not title1 or not title2:
        return 0.0

    t1 = title1.lower().strip()
    t2 = title2.lower().strip()

    return SequenceMatcher(None, t1, t2).ratio()


def find_fuzzy_duplicates(conn) -> list[tuple[int, int]]:
    """
    Find pairs of jobs that are likely duplicates using:
    1. Same company + very similar title (>85% string similarity)
    2. Posted within 3 days of each other

    Args:
        conn: Database connection

    Returns:
        List of (keep_id, duplicate_id) pairs where keep_id is the older record
    """
    pairs = []

    with conn.cursor() as cur:
        cur.execute("""
            SELECT id, company, title, date_posted, date_discovered
            FROM jobs
            WHERE is_duplicate = FALSE
            ORDER BY company, date_discovered
        """)

        jobs = cur.fetchall()

    company_jobs: dict[str, list[tuple]] = {}
    for job in jobs:
        job_id, company, title, date_posted, date_discovered = job
        company_key = company.lower().strip() if company else ""
        if company_key not in company_jobs:
            company_jobs[company_key] = []
        company_jobs[company_key].append((job_id, title, date_posted, date_discovered))

    for company_key, company_job_list in company_jobs.items():
        if len(company_job_list) < 2:
            continue

        for i, job1 in enumerate(company_job_list):
            for job2 in company_job_list[i + 1:]:
                id1, title1, date1, discovered1 = job1
                id2, title2, date2, discovered2 = job2

                similarity = title_similarity(title1, title2)
                if similarity < 0.75:
                    continue

                if date1 and date2:
                    try:
                        days_apart = abs((date1 - date2).days)
                        if days_apart > 3:
                            continue
                    except (TypeError, AttributeError):
                        pass

                if discovered1 <= discovered2:
                    pairs.append((id1, id2))
                else:
                    pairs.append((id2, id1))

    return pairs


def mark_duplicates(conn, pairs: list[tuple[int, int]]) -> int:
    """
    Mark the duplicate_id jobs as is_duplicate=True, set duplicate_of.

    Args:
        conn: Database connection
        pairs: List of (keep_id, duplicate_id) tuples

    Returns:
        Number of jobs marked as duplicate
    """
    if not pairs:
        return 0

    marked = 0

    with conn.cursor() as cur:
        for keep_id, dup_id in pairs:
            cur.execute("""
                UPDATE jobs
                SET is_duplicate = TRUE, duplicate_of = %s
                WHERE id = %s AND is_duplicate = FALSE
                RETURNING id
            """, (keep_id, dup_id))

            if cur.fetchone():
                marked += 1

        conn.commit()

    return marked


def run_deduplication(conn) -> tuple[int, int]:
    """
    Run the full deduplication process.

    Args:
        conn: Database connection

    Returns:
        Tuple of (pairs_found, pairs_marked)
    """
    print("Running fuzzy deduplication...")

    pairs = find_fuzzy_duplicates(conn)
    print(f"  Found {len(pairs)} potential duplicate pairs")

    if pairs:
        marked = mark_duplicates(conn, pairs)
        print(f"  Marked {marked} jobs as duplicates")
    else:
        marked = 0

    return len(pairs), marked


def main() -> None:
    """Main entry point for running deduplication standalone."""
    import os
    from pathlib import Path
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).parent.parent / ".env")

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL not found in environment")
        return

    conn = psycopg2.connect(db_url)

    try:
        pairs_found, pairs_marked = run_deduplication(conn)
        print(f"\nDeduplication complete: {pairs_found} pairs found, {pairs_marked} newly marked")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
