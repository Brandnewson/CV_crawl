"""Job search module using JobSpy to aggregate jobs from multiple sources."""

from __future__ import annotations

from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from datetime import date, datetime
from pathlib import Path
from typing import Any
import logging
import os
import time

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

SCORING_PROFILE_PATH = Path(__file__).parent.parent / "profile" / "scoring_profile.yaml"
TIMEOUT_LADDER_SECONDS = (60, 90, 120)
RETRY_COOLDOWN_SECONDS = 20
CALL_COOLDOWN_SECONDS = 5
DEFAULT_SITES = ["linkedin", "glassdoor", "indeed"]
TARGET_SITES = set(DEFAULT_SITES)

INDEED_COUNTRY_BY_CITY = {
    "london": "uk",
    "toronto": "canada",
    "new york": "usa",
    "san francisco": "usa",
    "seattle": "usa",
}

COUNTRY_ALIASES = {
    "ca": "canada",
    "can": "canada",
    "canada": "canada",
    "uk": "uk",
    "united kingdom": "uk",
    "gb": "uk",
    "gbr": "uk",
    "us": "usa",
    "usa": "usa",
    "united states": "usa",
    "united states of america": "usa",
}


def load_config() -> dict:
    """Load configuration from config.yaml."""
    config_path = Path(__file__).parent / "config.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_scoring_profile() -> dict[str, Any]:
    """Load scoring profile used as city source of truth."""
    if not SCORING_PROFILE_PATH.exists():
        return {}
    with open(SCORING_PROFILE_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _dedupe_keep_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        value = str(item or "").strip()
        if not value:
            continue
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(value)
    return out


def resolve_city_targets(config: dict[str, Any], scoring_profile: dict[str, Any]) -> tuple[list[str], str]:
    """Resolve city targets with profile-first behavior and legacy fallback."""
    preferred = scoring_profile.get("locations", {}).get("preferred", [])
    preferred = _dedupe_keep_order([str(v) for v in preferred])
    if preferred:
        return preferred, "scoring_profile.locations.preferred"

    search_cfg = config.get("search", {})
    config_locations = search_cfg.get("locations", [])
    if isinstance(config_locations, str):
        config_locations = [config_locations]
    config_locations = _dedupe_keep_order([str(v) for v in config_locations])
    if config_locations:
        return config_locations, "discovery.config.search.locations"

    legacy_location = str(search_cfg.get("location", "")).strip()
    if legacy_location:
        return [legacy_location], "discovery.config.search.location"
    return ["London"], "default"


def _city_key(city: str) -> str:
    return str(city or "").split(",", 1)[0].strip().lower()


def _normalize_country_value(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return "uk"
    normalized = raw.lower()
    return COUNTRY_ALIASES.get(normalized, normalized)


def resolve_indeed_country(city: str, fallback_country: str) -> str:
    """Map target city to Indeed country code with fallback."""
    city_norm = _city_key(city)
    if city_norm in INDEED_COUNTRY_BY_CITY:
        return INDEED_COUNTRY_BY_CITY[city_norm]
    return _normalize_country_value(fallback_country)


def _site_location(city: str, site: str) -> str:
    if site == "glassdoor":
        return str(city).split(",", 1)[0].strip()
    return str(city).strip()


def _scrape_once(scrape_kwargs: dict[str, Any], timeout_seconds: int):
    from jobspy import scrape_jobs

    site_names = scrape_kwargs.get("site_name", [])
    site = str(site_names[0]).strip().lower() if site_names else "unknown"
    jobspy_logger_name = f"JobSpy:{site.capitalize()}"
    captured_errors: list[str] = []

    class _CaptureErrorsHandler(logging.Handler):
        def emit(self, record) -> None:  # type: ignore[override]
            if record.levelno >= logging.ERROR:
                captured_errors.append(str(record.getMessage()))

    handler = _CaptureErrorsHandler()
    jobspy_logger = logging.getLogger(jobspy_logger_name)
    old_level = jobspy_logger.level
    jobspy_logger.addHandler(handler)
    if old_level > logging.ERROR:
        jobspy_logger.setLevel(logging.ERROR)

    with ThreadPoolExecutor(max_workers=1) as executor:
        try:
            future = executor.submit(scrape_jobs, **scrape_kwargs)
            try:
                jobs_df = future.result(timeout=timeout_seconds)
                has_rows = jobs_df is not None and len(jobs_df) > 0
                if captured_errors and not has_rows:
                    return None, RuntimeError(
                        f"{jobspy_logger_name} logged error: {captured_errors[0]}"
                    )
                return jobs_df, None
            except FuturesTimeoutError:
                future.cancel()
                return None, "timeout"
            except Exception as exc:  # pylint: disable=broad-except
                return None, exc
        finally:
            jobspy_logger.removeHandler(handler)
            jobspy_logger.setLevel(old_level)


def _is_non_retryable_scrape_error(err: Any) -> bool:
    """Return True for deterministic config/input errors that should fail fast."""
    msg = str(err or "").lower()
    markers = (
        "invalid country string",
        "invalid site",
        "invalid site_name",
        "missing required positional argument",
        "got an unexpected keyword argument",
    )
    return any(marker in msg for marker in markers)


def run_search_combo(config: dict[str, Any], search_term: str, city: str, site: str) -> dict[str, Any]:
    """Run one term x city x site scrape with timeout ladder and retry cooldown."""
    search_cfg = config.get("search", {})
    site_location = _site_location(city, site)
    fallback_country = search_cfg.get("country_indeed", "UK")
    country_indeed = resolve_indeed_country(city, fallback_country)

    scrape_kwargs = {
        "site_name": [site],
        "search_term": search_term,
        "location": site_location,
        "results_wanted": int(search_cfg.get("results_wanted", 30)),
        "hours_old": int(search_cfg.get("hours_old", 25)),
        "country_indeed": country_indeed,
        "linkedin_fetch_description": bool(search_cfg.get("linkedin_fetch_description", True)) if site == "linkedin" else False,
        "description_format": search_cfg.get("description_format", "markdown"),
        "easy_apply": False,
    }

    attempts: list[dict[str, Any]] = []
    final_jobs_df = None
    final_status = "failed"
    final_error = ""
    started = time.time()

    for idx, timeout_seconds in enumerate(TIMEOUT_LADDER_SECONDS, start=1):
        attempt_start = time.time()
        jobs_df, err = _scrape_once(scrape_kwargs=scrape_kwargs, timeout_seconds=timeout_seconds)
        attempts.append(
            {
                "attempt": idx,
                "timeout_seconds": timeout_seconds,
                "duration_seconds": round(time.time() - attempt_start, 2),
                "result": "ok" if err is None else ("timeout" if err == "timeout" else "error"),
                "error": "" if err in (None, "timeout") else str(err),
            }
        )

        if err is None:
            final_jobs_df = jobs_df
            final_status = "ok"
            break

        if err != "timeout" and _is_non_retryable_scrape_error(err):
            final_status = "failed"
            final_error = str(err)
            break

        is_last = idx == len(TIMEOUT_LADDER_SECONDS)
        if is_last:
            if err == "timeout":
                final_status = "timeout"
                final_error = f"timed_out_after_{timeout_seconds}s"
            else:
                final_status = "failed"
                final_error = str(err)
            break

        time.sleep(RETRY_COOLDOWN_SECONDS)

    jobs: list[dict[str, Any]] = []
    if final_jobs_df is not None and len(final_jobs_df) > 0:
        for _, row in final_jobs_df.iterrows():
            jobs.append(normalise_job(row, search_term=search_term))

    return {
        "search_term": search_term,
        "city": city,
        "site": site,
        "status": final_status,
        "error": final_error,
        "attempts": attempts,
        "duration_seconds": round(time.time() - started, 2),
        "jobs": jobs,
        "jobs_found": len(jobs),
    }


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
            if hasattr(raw_row, "get"):
                value = raw_row.get(key, default)
            else:
                value = getattr(raw_row, key, default)
            if value is None or (hasattr(value, "__class__") and str(value) == "nan"):
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
    elif hasattr(date_posted, "date"):
        date_posted = date_posted.date()
    elif isinstance(date_posted, str):
        try:
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


def insert_jobs(jobs: list[dict], conn, search_term: str) -> tuple[int, int, dict[str, Any]]:
    """Insert jobs into database and enrich inserted/updated rows."""
    total_attempted = len(jobs)
    new_inserted = 0
    enrichment_summary = {
        "llm_used": 0,
        "fallback_used": 0,
        "error_types": {},
    }

    with conn.cursor() as cur:
        for job in jobs:
            try:
                cur.execute("SAVEPOINT job_insert")
                cur.execute(
                    """
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
                """,
                    (
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
                    ),
                )
                result = cur.fetchone()
                if result:
                    inserted_job_id, is_new_row = result[0], result[1]
                    if is_new_row:
                        cur.execute(
                            """
                            INSERT INTO job_status (job_id, status)
                            VALUES (%s, 'new')
                            ON CONFLICT (job_id) DO NOTHING
                        """,
                            (inserted_job_id,),
                        )

                    desc = job["job_description_raw"] or ""
                    if desc:
                        enrichment = build_enrichment(desc)
                        if enrichment.get("llm_used"):
                            enrichment_summary["llm_used"] += 1
                        if enrichment.get("fallback_used"):
                            enrichment_summary["fallback_used"] += 1
                            error_type = str(enrichment.get("error_type") or "unknown")
                            enrichment_summary["error_types"][error_type] = (
                                enrichment_summary["error_types"].get(error_type, 0) + 1
                            )
                        cur.execute(
                            """
                            UPDATE jobs
                            SET enrichment_keywords = %s,
                                enrichment_version = %s,
                                enriched_at = %s
                            WHERE id = %s
                            """,
                            (
                                psycopg2.extras.Json(
                                    {
                                        "technologies": enrichment["technologies"],
                                        "skills": enrichment["skills"],
                                        "abilities": enrichment["abilities"],
                                        "llm_status": {
                                            "llm_used": enrichment.get("llm_used", False),
                                            "fallback_used": enrichment.get("fallback_used", False),
                                            "error_type": enrichment.get("error_type"),
                                        },
                                    }
                                ),
                                enrichment["version"],
                                datetime.fromisoformat(enrichment["enriched_at"]),
                                inserted_job_id,
                            ),
                        )
                    if is_new_row:
                        new_inserted += 1
            except Exception as e:  # pylint: disable=broad-except
                cur.execute("ROLLBACK TO SAVEPOINT job_insert")
                print(f"Error inserting job '{job.get('title', 'unknown')}': {e}")
            finally:
                cur.execute("RELEASE SAVEPOINT job_insert")

        conn.commit()

    return total_attempted, new_inserted, enrichment_summary


def log_search_run(conn, search_term: str, source: str, jobs_found: int, jobs_new: int, duration: float) -> None:
    """Log a search run to the search_runs table."""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO search_runs (search_term, source, jobs_found, jobs_new, duration_secs)
            VALUES (%s, %s, %s, %s, %s)
        """,
            (search_term, source, jobs_found, jobs_new, duration),
        )
        conn.commit()


def _build_coverage_report(combo_results: list[dict[str, Any]], expected_combos: int) -> dict[str, Any]:
    report: dict[str, Any] = {
        "expected_combos": expected_combos,
        "attempted_combos": len(combo_results),
        "succeeded_combos": 0,
        "timed_out_combos": 0,
        "failed_combos": 0,
        "per_site": {},
        "per_city": {},
    }

    site_counts: defaultdict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    city_counts: defaultdict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for item in combo_results:
        status = str(item.get("status", "failed"))
        site = str(item.get("site", "unknown"))
        city = str(item.get("city", "unknown"))

        site_counts[site]["attempted"] += 1
        city_counts[city]["attempted"] += 1

        if status == "ok":
            report["succeeded_combos"] += 1
            site_counts[site]["succeeded"] += 1
            city_counts[city]["succeeded"] += 1
        elif status == "timeout":
            report["timed_out_combos"] += 1
            site_counts[site]["timed_out"] += 1
            city_counts[city]["timed_out"] += 1
        else:
            report["failed_combos"] += 1
            site_counts[site]["failed"] += 1
            city_counts[city]["failed"] += 1

    report["per_site"] = {k: dict(v) for k, v in site_counts.items()}
    report["per_city"] = {k: dict(v) for k, v in city_counts.items()}
    return report


def main() -> None:
    """Main entry point for the job search script."""
    print("=" * 60)
    print("Job Pipeline - Discovery Search")
    print("=" * 60)

    config = load_config()
    scoring_profile = load_scoring_profile()

    search_cfg = config.get("search", {})
    search_terms = [str(v).strip() for v in search_cfg.get("search_terms", []) if str(v).strip()]
    sites_raw = search_cfg.get("site_name", DEFAULT_SITES)
    if isinstance(sites_raw, str):
        sites = [sites_raw]
    else:
        sites = [str(v).strip().lower() for v in sites_raw if str(v).strip()]
    sites = [site for site in _dedupe_keep_order(sites or DEFAULT_SITES) if site in TARGET_SITES]
    if not sites:
        sites = DEFAULT_SITES[:]

    cities, city_source = resolve_city_targets(config=config, scoring_profile=scoring_profile)

    print(f"\nLoaded {len(search_terms)} search terms")
    print(f"Sites: {', '.join(sites)}")
    print(f"Resolved cities ({city_source}): {', '.join(cities)}")
    print(
        "Timeout ladder: "
        f"{TIMEOUT_LADDER_SECONDS[0]}s -> {TIMEOUT_LADDER_SECONDS[1]}s -> {TIMEOUT_LADDER_SECONDS[2]}s"
        f" | retry cooldown={RETRY_COOLDOWN_SECONDS}s | call cooldown={CALL_COOLDOWN_SECONDS}s"
    )
    print("LinkedIn easy_apply excluded at query-time: true")
    print()

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL not found in environment")
        return

    try:
        conn = psycopg2.connect(db_url)
        print("Connected to database\n")
    except Exception as e:  # pylint: disable=broad-except
        print(f"ERROR: Could not connect to database: {e}")
        return

    total_found = 0
    total_new = 0
    total_enrichment = {"llm_used": 0, "fallback_used": 0, "error_types": {}}
    combo_results: list[dict[str, Any]] = []

    for term in search_terms:
        print(f"Searching term: '{term}'")

        for city in cities:
            for site in sites:
                print(f"  Combo -> site={site}, city={city}")
                combo = run_search_combo(config=config, search_term=term, city=city, site=site)
                combo_results.append(combo)

                jobs = combo["jobs"]
                inserted = 0
                enrichment = {"llm_used": 0, "fallback_used": 0, "error_types": {}}
                if combo["status"] == "ok" and jobs:
                    attempted, inserted, enrichment = insert_jobs(jobs=jobs, conn=conn, search_term=term)
                    total_found += attempted
                    total_new += inserted
                    total_enrichment["llm_used"] += enrichment["llm_used"]
                    total_enrichment["fallback_used"] += enrichment["fallback_used"]
                    for err, count in enrichment["error_types"].items():
                        total_enrichment["error_types"][err] = total_enrichment["error_types"].get(err, 0) + count

                log_search_run(
                    conn=conn,
                    search_term=term,
                    source=f"{site}|{city}",
                    jobs_found=int(combo.get("jobs_found", 0)),
                    jobs_new=int(inserted),
                    duration=float(combo.get("duration_seconds", 0.0)),
                )

                if combo["status"] == "ok":
                    print(
                        f"    ok: found={combo['jobs_found']} new={inserted} duration={combo['duration_seconds']}s"
                    )
                    if enrichment["llm_used"] or enrichment["fallback_used"]:
                        print(
                            "    Enrichment summary: "
                            f"llm_used={enrichment['llm_used']}, "
                            f"fallback_used={enrichment['fallback_used']}, "
                            f"error_types={enrichment['error_types'] or {}}"
                        )
                elif combo["status"] == "timeout":
                    print(
                        "    timeout: "
                        f"duration={combo['duration_seconds']}s "
                        f"error={combo.get('error', 'timeout')}"
                    )
                else:
                    print(
                        "    failed: "
                        f"duration={combo['duration_seconds']}s "
                        f"error={combo.get('error', 'unknown')}"
                    )

                time.sleep(CALL_COOLDOWN_SECONDS)

    coverage = _build_coverage_report(
        combo_results=combo_results,
        expected_combos=len(search_terms) * len(cities) * len(sites),
    )

    conn.close()

    print()
    print("=" * 60)
    print(
        "SUMMARY: "
        f"terms={len(search_terms)} cities={len(cities)} sites={len(sites)} "
        f"jobs_found={total_found} jobs_new={total_new}"
    )
    print(
        "ENRICHMENT FALLBACK SUMMARY: "
        f"llm_used={total_enrichment['llm_used']}, "
        f"fallback_used={total_enrichment['fallback_used']}, "
        f"error_types={total_enrichment['error_types'] or {}}"
    )
    print(
        "COVERAGE SUMMARY: "
        f"expected={coverage['expected_combos']} "
        f"attempted={coverage['attempted_combos']} "
        f"succeeded={coverage['succeeded_combos']} "
        f"timed_out={coverage['timed_out_combos']} "
        f"failed={coverage['failed_combos']}"
    )
    print(f"COVERAGE PER SITE: {coverage['per_site']}")
    print(f"COVERAGE PER CITY: {coverage['per_city']}")
    print("=" * 60)


if __name__ == "__main__":
    main()
