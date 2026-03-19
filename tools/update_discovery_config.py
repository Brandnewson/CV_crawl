"""Atomically update discovery/config.yaml from structured arguments."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

import yaml


DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "discovery" / "config.yaml"


def _load_config(path: Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _apply_updates(cfg: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    search = cfg.setdefault("search", {})
    scoring = cfg.setdefault("scoring", {})
    exclusions = cfg.setdefault("exclusions", {})

    if "search_terms" in updates:
        search["search_terms"] = updates["search_terms"]
    if "location" in updates:
        search["location"] = updates["location"]
    if "locations" in updates:
        search["locations"] = updates["locations"]
    if "sites" in updates:
        search["site_name"] = updates["sites"]
    if "results_wanted" in updates:
        search["results_wanted"] = int(updates["results_wanted"])
    if "hours_old" in updates:
        search["hours_old"] = int(updates["hours_old"])

    if "salary_floor" in updates:
        scoring["salary_floor"] = int(updates["salary_floor"])

    if "title_keywords" in updates:
        exclusions["title_keywords"] = updates["title_keywords"]
    if "description_keywords" in updates:
        exclusions["description_keywords"] = updates["description_keywords"]

    return cfg


def _atomic_write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", delete=False, encoding="utf-8", dir=path.parent, suffix=".tmp") as tf:
        yaml.dump(payload, tf, default_flow_style=False, allow_unicode=True, sort_keys=False)
        tmp_path = Path(tf.name)
    tmp_path.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Update discovery/config.yaml", allow_abbrev=False)
    parser.add_argument("--config-path", default=str(DEFAULT_CONFIG_PATH))
    parser.add_argument("--updates-json", help="Inline JSON object string with updates")
    parser.add_argument("--updates-file", help="Path to JSON object file with updates")
    parser.add_argument("--search-terms", help="Comma-separated search terms")
    parser.add_argument("--location")
    parser.add_argument("--locations", help="Comma-separated city list")
    parser.add_argument("--sites", help="Comma-separated sites")
    parser.add_argument("--results-wanted", type=int)
    parser.add_argument("--hours-old", type=int)
    parser.add_argument("--salary-floor", type=int)
    parser.add_argument("--title-keywords", help="Comma-separated title exclusion keywords")
    parser.add_argument("--description-keywords", help="Comma-separated description exclusion keywords")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    cfg_path = Path(args.config_path)
    cfg = _load_config(cfg_path)

    updates: dict[str, Any] = {}
    if args.updates_file:
        updates.update(json.loads(Path(args.updates_file).read_text(encoding="utf-8-sig")))
    if args.updates_json:
        updates.update(json.loads(args.updates_json))

    if args.search_terms is not None:
        updates["search_terms"] = _split_csv(args.search_terms)
    if args.location is not None:
        updates["location"] = args.location
    if args.locations is not None:
        updates["locations"] = _split_csv(args.locations)
    if args.sites is not None:
        updates["sites"] = _split_csv(args.sites)
    if args.results_wanted is not None:
        updates["results_wanted"] = args.results_wanted
    if args.hours_old is not None:
        updates["hours_old"] = args.hours_old
    if args.salary_floor is not None:
        updates["salary_floor"] = args.salary_floor
    if args.title_keywords is not None:
        updates["title_keywords"] = _split_csv(args.title_keywords)
    if args.description_keywords is not None:
        updates["description_keywords"] = _split_csv(args.description_keywords)

    new_cfg = _apply_updates(cfg, updates)
    _atomic_write_yaml(cfg_path, new_cfg)

    print(json.dumps({"config_path": str(cfg_path), "updates_applied": sorted(updates.keys())}, ensure_ascii=False))


if __name__ == "__main__":
    main()
