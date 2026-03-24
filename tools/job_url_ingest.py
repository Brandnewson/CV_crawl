"""Ingest a job posting URL for /cv-apply.

This utility:
1. Fetches a web page.
2. Extracts best-effort job title/company/location/description.
3. Upserts the job into PostgreSQL (unless --skip-db).
4. Writes cv-apply meta + JD text artifacts for downstream stages.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from datetime import date
from html import unescape
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen

import psycopg2
from dotenv import load_dotenv
from lxml import html as lxml_html

from clean_jd import clean_jd
from cv_apply_contract import ARTIFACT_DEFAULT_PATHS


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


def _normalise_space(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def _strip_tags(text: str) -> str:
    cleaned = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", text or "")
    cleaned = re.sub(r"(?s)<[^>]+>", " ", cleaned)
    return _normalise_space(unescape(cleaned))


def _parse_json_candidate(raw: str) -> Any:
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def _walk_json(node: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if isinstance(node, dict):
        out.append(node)
        for value in node.values():
            out.extend(_walk_json(value))
    elif isinstance(node, list):
        for item in node:
            out.extend(_walk_json(item))
    return out


def _extract_json_ld_fields(doc) -> dict[str, str]:
    scripts = doc.xpath("//script[@type='application/ld+json']/text()")
    records: list[dict[str, Any]] = []
    for block in scripts:
        parsed = _parse_json_candidate(block)
        if parsed is not None:
            records.extend(_walk_json(parsed))

    posting: dict[str, Any] | None = None
    for record in records:
        types = record.get("@type")
        if isinstance(types, list):
            type_names = {str(v).lower() for v in types}
        else:
            type_names = {str(types).lower()}
        if "jobposting" in type_names:
            posting = record
            break

    if not posting:
        return {}

    company = ""
    org = posting.get("hiringOrganization")
    if isinstance(org, dict):
        company = _normalise_space(str(org.get("name", "")))

    location = ""
    loc = posting.get("jobLocation")
    if isinstance(loc, list):
        loc = loc[0] if loc else {}
    if isinstance(loc, dict):
        address = loc.get("address", {})
        if isinstance(address, dict):
            parts = [
                _normalise_space(str(address.get("addressLocality", ""))),
                _normalise_space(str(address.get("addressRegion", ""))),
                _normalise_space(str(address.get("addressCountry", ""))),
            ]
            location = ", ".join([part for part in parts if part])

    description_raw = str(posting.get("description", "") or "")
    return {
        "title": _normalise_space(str(posting.get("title", ""))),
        "company": company,
        "location": location,
        "description": _strip_tags(description_raw),
    }


def _extract_meta(doc, *names: str) -> str:
    for name in names:
        values = doc.xpath(
            f"//meta[translate(@name,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz')='{name.lower()}']/@content"
        )
        if values:
            return _normalise_space(str(values[0]))
        values = doc.xpath(
            f"//meta[translate(@property,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz')='{name.lower()}']/@content"
        )
        if values:
            return _normalise_space(str(values[0]))
    return ""


def _extract_main_text(doc) -> str:
    for bad in doc.xpath("//script|//style|//noscript|//svg"):
        parent = bad.getparent()
        if parent is not None:
            parent.remove(bad)

    selectors = [
        "//*[contains(@id,'jobDescriptionText')]",
        "//*[contains(@id,'job-description')]",
        "//*[contains(@class,'job-description')]",
        "//*[contains(@class,'description') and contains(@class,'job')]",
        "//main",
        "//article",
        "//body",
    ]
    for selector in selectors:
        nodes = doc.xpath(selector)
        for node in nodes:
            text = _normalise_space(node.text_content())
            if len(text) >= 300:
                return text
    return ""


def _derive_company_from_title(title: str) -> str:
    parts = re.split(r"\s[|\-–]\s", title or "")
    if len(parts) >= 2:
        return _normalise_space(parts[-1])
    return ""


def _derive_company_from_url(url: str) -> str:
    host = urlparse(url).netloc.lower()
    host = re.sub(r"^www\.", "", host)
    company = host.split(".")[0] if host else "unknown"
    company = company.replace("-", " ").replace("_", " ").strip()
    return company.title() if company else "Unknown Company"


def fetch_and_extract(url: str, timeout_secs: int = 20) -> dict[str, str]:
    req = Request(url=url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=timeout_secs) as response:
        body = response.read()
        final_url = response.geturl()
        charset = response.headers.get_content_charset() or "utf-8"
    raw_html = body.decode(charset, errors="replace")
    doc = lxml_html.fromstring(raw_html)

    json_ld = _extract_json_ld_fields(doc)
    page_title = _normalise_space(
        "".join(doc.xpath("//title/text()")) or _extract_meta(doc, "og:title", "twitter:title")
    )

    description = (
        json_ld.get("description", "")
        or _extract_meta(doc, "description", "og:description", "twitter:description")
        or _extract_main_text(doc)
    )
    description = clean_jd(description)

    title = json_ld.get("title", "") or page_title
    title = clean_jd(title) if title else ""
    company = json_ld.get("company", "") or _derive_company_from_title(title)
    location = json_ld.get("location", "")

    if not company:
        company = _derive_company_from_url(final_url)
    if not title:
        title = "Untitled Role"

    return {
        "job_url": final_url,
        "job_title": _normalise_space(title),
        "company": _normalise_space(company),
        "location": _normalise_space(location),
        "description": description,
    }


def _load_db_url() -> str:
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    db_url = os.environ.get("DATABASE_URL", "").strip()
    if not db_url:
        raise RuntimeError("DATABASE_URL is required for URL ingestion DB upsert")
    return db_url


def upsert_manual_job(
    *,
    db_url: str,
    user_id: int,
    source: str,
    company: str,
    job_title: str,
    location: str,
    job_url: str,
    description: str,
) -> tuple[int, str]:
    external_id = hashlib.sha1(job_url.encode("utf-8")).hexdigest()[:24]
    summary = "Manually imported from URL for cv-apply"

    conn = psycopg2.connect(db_url)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id
                FROM jobs
                WHERE user_id = %s AND job_url = %s
                ORDER BY id DESC
                LIMIT 1
                """,
                (user_id, job_url),
            )
            row = cur.fetchone()
            if row:
                job_id = int(row[0])
                cur.execute(
                    """
                    UPDATE jobs
                    SET source = %s,
                        external_id = COALESCE(external_id, %s),
                        company = %s,
                        title = %s,
                        location = %s,
                        description = %s,
                        job_description_raw = %s,
                        date_discovered = NOW()
                    WHERE id = %s
                    """,
                    (source, external_id, company, job_title, location, description, description, job_id),
                )
                action = "updated"
            else:
                cur.execute(
                    """
                    INSERT INTO jobs (
                        user_id,
                        source,
                        external_id,
                        company,
                        title,
                        location,
                        job_url,
                        description,
                        job_description_raw,
                        date_posted,
                        search_term
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        user_id,
                        source,
                        external_id,
                        company,
                        job_title,
                        location,
                        job_url,
                        description,
                        description,
                        date.today(),
                        "manual_url",
                    ),
                )
                job_id = int(cur.fetchone()[0])
                action = "inserted"

            cur.execute(
                """
                INSERT INTO job_status (user_id, job_id, fit_score, fit_summary, status, status_updated)
                VALUES (%s, %s, %s, %s, %s, NOW())
                ON CONFLICT (job_id) DO UPDATE SET
                    status = EXCLUDED.status,
                    status_updated = EXCLUDED.status_updated,
                    fit_score = COALESCE(job_status.fit_score, EXCLUDED.fit_score),
                    fit_summary = COALESCE(job_status.fit_summary, EXCLUDED.fit_summary)
                """,
                (user_id, job_id, 1.0, summary, "new"),
            )

        conn.commit()
        return job_id, action
    finally:
        conn.close()


def ingest_job_url(
    *,
    url: str,
    user_id: int = 1,
    title_override: str = "",
    company_override: str = "",
    location_override: str = "",
    skip_db: bool = False,
) -> dict[str, Any]:
    extracted = fetch_and_extract(url)
    if title_override.strip():
        extracted["job_title"] = clean_jd(title_override)
    if company_override.strip():
        extracted["company"] = clean_jd(company_override)
    if location_override.strip():
        extracted["location"] = clean_jd(location_override)

    if not extracted["description"]:
        raise RuntimeError("Could not extract a job description from URL")

    payload: dict[str, Any] = {
        "source": "manual_url",
        "job_url": extracted["job_url"],
        "company": extracted["company"],
        "job_title": extracted["job_title"],
        "location": extracted["location"],
        "description": extracted["description"],
    }

    if skip_db:
        payload["job_id"] = None
        payload["db_action"] = "skipped"
        return payload

    db_url = _load_db_url()
    job_id, action = upsert_manual_job(
        db_url=db_url,
        user_id=user_id,
        source=payload["source"],
        company=payload["company"],
        job_title=payload["job_title"],
        location=payload["location"],
        job_url=payload["job_url"],
        description=payload["description"],
    )
    payload["job_id"] = job_id
    payload["db_action"] = action
    return payload


def _write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def write_artifacts(payload: dict[str, Any], meta_out: Path, jd_out: Path) -> None:
    if payload.get("job_id") is None:
        raise RuntimeError("Cannot write cv-apply meta without a DB-backed job_id")
    meta = {
        "job_id": int(payload["job_id"]),
        "company": payload["company"],
        "job_title": payload["job_title"],
        "location": payload.get("location", ""),
        "job_url": payload["job_url"],
        "source": payload.get("source", "manual_url"),
        "job_description": payload.get("description", ""),
    }
    _write(meta_out, meta)
    jd_out.parent.mkdir(parents=True, exist_ok=True)
    jd_out.write_text(str(payload.get("description", "")), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest job URL and prepare cv-apply artifacts")
    parser.add_argument("--url", required=True, help="Job posting URL")
    parser.add_argument("--user-id", type=int, default=1)
    parser.add_argument("--job-title", default="", help="Optional override")
    parser.add_argument("--company", default="", help="Optional override")
    parser.add_argument("--location", default="", help="Optional override")
    parser.add_argument("--skip-db", action="store_true")
    parser.add_argument("--meta-out", default=str(ARTIFACT_DEFAULT_PATHS["meta"]))
    parser.add_argument("--jd-out", default=str(ARTIFACT_DEFAULT_PATHS["jd_text"]))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = ingest_job_url(
        url=args.url,
        user_id=args.user_id,
        title_override=args.job_title,
        company_override=args.company,
        location_override=args.location,
        skip_db=bool(args.skip_db),
    )
    if not args.skip_db:
        write_artifacts(
            payload=payload,
            meta_out=Path(args.meta_out),
            jd_out=Path(args.jd_out),
        )
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
