"""Script entrypoint for safe JD keyword extraction."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from agent.jd_parser import extract_keywords_safe


DEFAULT_JD_PATH = Path(r"C:\Code\CV_crawl\.cv-apply-jd-tmp.txt")


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract JD keywords via safe wrapper", allow_abbrev=False)
    parser.add_argument("--jd-path", default=str(DEFAULT_JD_PATH), help="Path to raw JD text")
    parser.add_argument("--job-title", default="", help="Job title for role-family classification")
    parser.add_argument("--user-id", type=int, default=1)
    parser.add_argument("--out", help="Optional output JSON path")
    parser.add_argument("--cache-out", help="Optional cache JSON path")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    jd_path = Path(args.jd_path)
    if not jd_path.exists():
        raise FileNotFoundError(f"JD file not found: {jd_path}")

    raw_jd = jd_path.read_text(encoding="utf-8-sig")
    payload = extract_keywords_safe(
        job_description=raw_jd,
        job_title=args.job_title,
        user_id=args.user_id,
    )

    if args.out:
        _write(Path(args.out), payload)
    if args.cache_out:
        _write(Path(args.cache_out), payload)

    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
