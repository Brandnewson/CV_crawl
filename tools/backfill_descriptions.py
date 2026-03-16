"""Backfill job descriptions for existing DB rows with empty descriptions.

Fetches LinkedIn descriptions via the guest API and Indeed descriptions via
direct page scraping, then updates the DB.

Usage:
    uv run --project "C:/Code/CV_CoverLetter_Generator_Agentic_Pipeline/job-pipeline" \
        python "C:/Code/CV_crawl/tools/backfill_descriptions.py" [--dry-run] [--limit N]
"""

import argparse
import os
import sys
import time
from pathlib import Path

import psycopg2
import requests
from bs4 import BeautifulSoup

sys.path.insert(0, r"C:\Code\CV_CoverLetter_Generator_Agentic_Pipeline\job-pipeline")
from discovery.enrichment import normalize_job_description_markdown

# Load .env from CV_crawl
from dotenv import load_dotenv
load_dotenv(Path(r"C:\Code\CV_crawl\.env"))


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9",
}


def fetch_linkedin_description(job_id: str) -> str:
    """Fetch description from LinkedIn guest API. Returns markdown text or empty string."""
    numeric_id = job_id.replace("li-", "")
    url = f"https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{numeric_id}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code == 429:
            print(f"    Rate limited (429) on job {job_id}")
            return ""
        if r.status_code != 200:
            print(f"    HTTP {r.status_code} for job {job_id}")
            return ""
        soup = BeautifulSoup(r.text, "html.parser")
        desc_div = soup.find("div", {"class": "show-more-less-html__markup"})
        if not desc_div:
            return ""
        try:
            from markdownify import markdownify as md
            return md(str(desc_div)).strip()
        except ImportError:
            return desc_div.get_text(separator="\n").strip()
    except Exception as e:
        print(f"    Error fetching {job_id}: {e}")
        return ""


def fetch_indeed_description(job_url: str) -> str:
    """Fetch description from Indeed job page. Returns text or empty string."""
    try:
        r = requests.get(job_url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return ""
        soup = BeautifulSoup(r.text, "html.parser")
        desc_div = (
            soup.find("div", {"id": "jobDescriptionText"})
            or soup.find("div", {"class": "jobsearch-jobDescriptionText"})
        )
        if not desc_div:
            return ""
        try:
            from markdownify import markdownify as md
            return md(str(desc_div)).strip()
        except ImportError:
            return desc_div.get_text(separator="\n").strip()
    except Exception as e:
        print(f"    Error fetching {job_url}: {e}")
        return ""


def backfill(dry_run: bool = False, limit: int = 0, delay: float = 1.5) -> None:
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL not set")
        sys.exit(1)

    conn = psycopg2.connect(db_url)

    with conn.cursor() as cur:
        query = """
            SELECT id, source, external_id, job_url
            FROM jobs
            WHERE (description IS NULL OR description = '')
              AND source IN ('linkedin', 'indeed')
            ORDER BY id
        """
        if limit:
            query += f" LIMIT {limit}"
        cur.execute(query)
        rows = cur.fetchall()

    print(f"Found {len(rows)} jobs with empty descriptions")
    if dry_run:
        print("[DRY RUN — no DB writes]")

    updated = 0
    skipped = 0

    for i, (job_id, source, external_id, job_url) in enumerate(rows, 1):
        print(f"[{i}/{len(rows)}] id={job_id} source={source} ext={external_id}")

        raw_text = ""
        if source == "linkedin":
            raw_text = fetch_linkedin_description(external_id)
        elif source == "indeed":
            raw_text = fetch_indeed_description(job_url)

        if not raw_text:
            print("    -> no description found, skipping")
            skipped += 1
            time.sleep(delay)
            continue

        description = normalize_job_description_markdown(raw_text)
        print(f"    -> {len(description)} chars")

        if not dry_run:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE jobs SET description = %s, job_description_raw = %s WHERE id = %s",
                    (description, description, job_id),
                )
            conn.commit()
        updated += 1

        time.sleep(delay)

    conn.close()
    print(f"\nDone. Updated: {updated}, Skipped: {skipped}")


def main():
    parser = argparse.ArgumentParser(description="Backfill job descriptions")
    parser.add_argument("--dry-run", action="store_true", help="Don't write to DB")
    parser.add_argument("--limit", type=int, default=0, help="Max jobs to process (0=all)")
    parser.add_argument("--delay", type=float, default=1.5, help="Seconds between requests")
    args = parser.parse_args()
    backfill(dry_run=args.dry_run, limit=args.limit, delay=args.delay)


if __name__ == "__main__":
    main()
