"""Job search module using JobSpy to aggregate jobs from multiple sources."""

from pathlib import Path
from typing import Any
import os
import time
from datetime import date
from datetime import datetime

import psycopg2
import psycopg2.extras
import yaml
from dotenv import load_dotenv

from discovery.enrichment import (
    build_enrichment,
    normalize_company_description_text,
    normalize_job_description_markdown,
)

# Load environment variables
load_dotenv(Path(__file__).parent.parent / ".env")


def load_config() -> dict:
    """Load configuration from config.yaml."""
    config_path = Path(__file__).parent / "config.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def run_search(config: dict, search_term: str) -> list[dict]:
    """
    Run JobSpy for one search term across all configured sources.

    Runs each source individually for fault isolation - a failure on one
    source (e.g., rate limiting) won't affect others.

    Args:
        config: Configuration dictionary with search settings
        search_term: The job search query

    Returns:
        List of normalised job dictionaries from all successful sources
    """
    from jobspy import scrape_jobs

    search_config = config.get("search", {})
    sites = search_config.get("site_name", ["linkedin", "indeed"])

    # Ensure sites is a list
    if isinstance(sites, str):
        sites = [sites]

    all_jobs = []

    # Run each source individually for fault isolation
    for site in sites:
        try:
            # Glassdoor requires city-level location without "UK" suffix
            location = search_config.get("location", "London, UK")
            if site == "glassdoor":
                location = location.split(",")[0].strip()

            jobs_df = scrape_jobs(
                site_name=[site],
                search_term=search_term,
                location=location,
                results_wanted=search_config.get("results_wanted", 30),
                hours_old=search_config.get("hours_old", 25),
                country_indeed=search_config.get("country_indeed", "UK") if site == "indeed" else "usa",
                linkedin_fetch_description=search_config.get("linkedin_fetch_description", True) if site == "linkedin" else False,
                description_format=search_config.get("description_format", "markdown"),
            )

            if jobs_df is not None and len(jobs_df) > 0:
                for _, row in jobs_df.iterrows():
                    job = normalise_job(row, search_term)
                    all_jobs.append(job)
                print(f"  {site}: {len(jobs_df)} jobs")
            else:
                print(f"  {site}: 0 jobs")

        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg:
                print(f"  {site}: rate limited (429)")
            elif "location not parsed" in error_msg.lower():
                print(f"  {site}: location not supported")
            else:
                print(f"  {site}: error - {error_msg[:80]}")

    return all_jobs


def normalise_job(raw_row: Any, search_term: str = "") -> dict:
    """
    Convert a JobSpy DataFrame row to the canonical job dict matching the DB schema.

    Args:
        raw_row: A row from JobSpy DataFrame (or dict-like object)
        search_term: The search term used to find this job

    Returns:
        Dictionary with normalised job data matching DB schema
    """
    def safe_get(key: str, default: Any = None) -> Any:
        """Safely get a value from the row, handling various input types."""
        try:
            if hasattr(raw_row, 'get'):
                value = raw_row.get(key, default)
            else:
                value = getattr(raw_row, key, default)
            if value is None or (hasattr(value, '__class__') and str(value) == 'nan'):
                return default
            import pandas as pd
            if pd.isna(value):
                return default
            return value
        except (AttributeError, KeyError):
            return default

    def pick_first_text(keys: list[str]) -> str:
        for key in keys:
            value = safe_get(key, "")
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""

    # Determine remote type
    is_remote = safe_get("is_remote", False)
    if is_remote is True or str(is_remote).lower() == "true":
        remote_type = "remote"
    elif is_remote is False or str(is_remote).lower() == "false":
        remote_type = "onsite"
    else:
        remote_type = "hybrid" if "hybrid" in str(is_remote).lower() else "onsite"

    # Parse salary values
    salary_min = safe_get("min_amount")
    salary_max = safe_get("max_amount")

    if salary_min is not None:
        try:
            salary_min = int(float(salary_min))
        except (ValueError, TypeError):
            salary_min = None

    if salary_max is not None:
        try:
            salary_max = int(float(salary_max))
        except (ValueError, TypeError):
            salary_max = None

    # Parse date_posted
    date_posted = safe_get("date_posted")
    if date_posted is None:
        date_posted = date.today()
    elif hasattr(date_posted, 'date'):
        date_posted = date_posted.date()
    elif isinstance(date_posted, str):
        try:
            from datetime import datetime
            date_posted = datetime.strptime(date_posted, "%Y-%m-%d").date()
        except ValueError:
            date_posted = date.today()

    job_description_raw = normalize_job_description_markdown(
        pick_first_text(["description", "job_description"])
    )
    company_description_raw = normalize_company_description_text(
        pick_first_text(["company_description", "company_about", "about_company"])
    )

    return {
        "source": safe_get("site", "unknown"),
        "external_id": str(safe_get("id", "")),
        "company": safe_get("company", "Unknown Company"),
        "title": safe_get("title", "Unknown Title"),
        "location": safe_get("location", ""),
        "remote_type": remote_type,
        "salary_min": salary_min,
        "salary_max": salary_max,
        "currency": safe_get("currency", "GBP"),
        "job_url": safe_get("job_url", ""),
        "description": job_description_raw,
        "job_description_raw": job_description_raw,
        "company_description_raw": company_description_raw,
        "date_posted": date_posted,
        "search_term": search_term,
    }


def insert_jobs(jobs: list[dict], conn, search_term: str) -> tuple[int, int]:
    """
    Insert jobs into database.

    Args:
        jobs: List of normalised job dictionaries
        conn: Database connection
        search_term: The search term used (for logging)

    Returns:
        Tuple of (total_attempted, new_inserted)
    """
    total_attempted = len(jobs)
    new_inserted = 0

    with conn.cursor() as cur:
        for job in jobs:
            try:
                cur.execute("SAVEPOINT job_insert")
                cur.execute("""
                    INSERT INTO jobs (
                        source, external_id, company, title, location,
                        remote_type, salary_min, salary_max, currency,
                        job_url, description, job_description_raw, company_description_raw,
                        date_posted, search_term
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (source, external_id) DO UPDATE SET
                        description = CASE
                            WHEN EXCLUDED.description != '' THEN EXCLUDED.description
                            ELSE jobs.description
                        END,
                        job_description_raw = CASE
                            WHEN EXCLUDED.job_description_raw != '' THEN EXCLUDED.job_description_raw
                            ELSE jobs.job_description_raw
                        END,
                        company_description_raw = COALESCE(NULLIF(EXCLUDED.company_description_raw, ''), jobs.company_description_raw),
                        title = EXCLUDED.title,
                        location = EXCLUDED.location,
                        job_url = EXCLUDED.job_url
                    RETURNING id, (xmax = 0) AS inserted
                """, (
                    job["source"],
                    job["external_id"],
                    job["company"],
                    job["title"],
                    job["location"],
                    job["remote_type"],
                    job["salary_min"],
                    job["salary_max"],
                    job["currency"],
                    job["job_url"],
                    job["description"],
                    job["job_description_raw"],
                    job["company_description_raw"],
                    job["date_posted"],
                    job["search_term"],
                ))
                result = cur.fetchone()
                if result:
                    inserted_job_id, is_new_row = result[0], result[1]
                    if is_new_row:
                        cur.execute("""
                            INSERT INTO job_status (job_id, status)
                            VALUES (%s, 'new')
                            ON CONFLICT (job_id) DO NOTHING
                        """, (inserted_job_id,))

                    desc = job["job_description_raw"] or ""
                    if desc:
                        enrichment = build_enrichment(desc)
                        cur.execute(
                            """
                            UPDATE jobs
                            SET enrichment_keywords = %s,
                                enrichment_version = %s,
                                enriched_at = %s
                            WHERE id = %s
                            """,
                            (
                                psycopg2.extras.Json({
                                    "technologies": enrichment["technologies"],
                                    "skills": enrichment["skills"],
                                    "abilities": enrichment["abilities"],
                                }),
                                enrichment["version"],
                                datetime.fromisoformat(enrichment["enriched_at"]),
                                inserted_job_id,
                            ),
                        )
                    if is_new_row:
                        new_inserted += 1
            except Exception as e:
                cur.execute("ROLLBACK TO SAVEPOINT job_insert")
                print(f"Error inserting job '{job.get('title', 'unknown')}': {e}")
            finally:
                cur.execute("RELEASE SAVEPOINT job_insert")

        conn.commit()

    return total_attempted, new_inserted


def log_search_run(conn, search_term: str, source: str, jobs_found: int, jobs_new: int, duration: float) -> None:
    """Log a search run to the search_runs table."""
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO search_runs (search_term, source, jobs_found, jobs_new, duration_secs)
            VALUES (%s, %s, %s, %s, %s)
        """, (search_term, source, jobs_found, jobs_new, duration))
        conn.commit()


def main() -> None:
    """Main entry point for the job search script."""
    print("=" * 60)
    print("Job Pipeline - Discovery Search")
    print("=" * 60)

    config = load_config()
    search_config = config.get("search", {})
    search_terms = search_config.get("search_terms", [])

    print(f"\nLoaded {len(search_terms)} search terms")
    print(f"Searching: {', '.join(search_config.get('site_name', []))}")
    print(f"Location: {search_config.get('location', 'Not specified')}")
    print()

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL not found in environment")
        return

    try:
        conn = psycopg2.connect(db_url)
        print("Connected to database\n")
    except Exception as e:
        print(f"ERROR: Could not connect to database: {e}")
        return

    total_found = 0
    total_new = 0

    for term in search_terms:
        print(f"Searching: '{term}'...")
        start_time = time.time()

        try:
            jobs = run_search(config, term)
            duration = time.time() - start_time

            if jobs:
                attempted, inserted = insert_jobs(jobs, conn, term)
                total_found += attempted
                total_new += inserted

                sources = ", ".join(search_config.get("site_name", []))
                log_search_run(conn, term, sources, attempted, inserted, duration)

                print(f"  Found {attempted} jobs, {inserted} new ({duration:.1f}s)")
            else:
                print(f"  No jobs found ({duration:.1f}s)")

        except Exception as e:
            print(f"  Error: {e}")

    conn.close()

    print()
    print("=" * 60)
    print(f"SUMMARY: Searched {len(search_terms)} terms — {total_found} found, {total_new} new")
    print("=" * 60)


if __name__ == "__main__":
    main()
