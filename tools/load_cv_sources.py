"""Load CV source files and print a single JSON payload."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def _load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Load CV source files", allow_abbrev=False)
    parser.add_argument("--store-path", default=r"C:\Code\CV_crawl\.cv-harvest-store.json")
    parser.add_argument("--work-exp-path", default=r"C:\Code\CV_crawl\.cv-work-experience.json")
    parser.add_argument("--cache-path", default=r"C:\Code\CV_crawl\.experience-cache.json")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    store_path = Path(args.store_path)
    work_exp_path = Path(args.work_exp_path)
    cache_path = Path(args.cache_path)

    if not store_path.exists():
        print("ERROR: .cv-harvest-store.json not found. Run /cv-harvest first.", file=sys.stderr)
        sys.exit(1)
    if not work_exp_path.exists():
        print("ERROR: .cv-work-experience.json not found.", file=sys.stderr)
        sys.exit(1)

    payload = {
        "store": _load_json(store_path, default={}),
        "work_exp": _load_json(work_exp_path, default={}),
        "cache": _load_json(cache_path, default={}) if cache_path.exists() else {},
    }
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
