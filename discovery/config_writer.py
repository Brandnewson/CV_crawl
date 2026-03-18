"""Write discovery/config.yaml from a user_preferences DB row.

Called after every POST /api/preferences to keep config.yaml in sync
with the DB as the single source of truth.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


_DEFAULT_CONFIG_PATH = Path(__file__).parent / "config.yaml"


def _build_config_dict(prefs: dict[str, Any]) -> dict[str, Any]:
    """Convert a ``user_preferences`` DB row to the config.yaml structure."""
    return {
        "search": {
            "site_name": ["linkedin", "indeed", "glassdoor", "google"],
            "linkedin_fetch_description": True,
            "description_format": "markdown",
            "search_terms": prefs.get("search_terms", []),
            "location": prefs.get("location", "London, UK"),
            "results_wanted": prefs.get("results_wanted", 30),
            "hours_old": prefs.get("hours_old", 25),
            "country_indeed": prefs.get("country_indeed", "UK"),
        },
        "scoring": {
            "salary_floor": prefs.get("salary_floor", 40000),
            "currency": prefs.get("currency", "GBP"),
        },
        "exclusions": {
            "title_keywords": prefs.get("excluded_title_keywords", []),
            "description_keywords": prefs.get("excluded_desc_keywords", []),
        },
    }


def write_config_yaml(
    prefs: dict[str, Any],
    path: Path = _DEFAULT_CONFIG_PATH,
) -> None:
    """Serialise *prefs* to *path* in the standard config.yaml format.

    Args:
        prefs: A ``user_preferences`` DB row (or equivalent dict).
        path: Destination YAML file path. Defaults to ``discovery/config.yaml``.
    """
    config = _build_config_dict(prefs)
    with open(path, "w", encoding="utf-8") as fh:
        yaml.dump(config, fh, default_flow_style=False, allow_unicode=True, sort_keys=False)


def read_config_yaml(path: Path = _DEFAULT_CONFIG_PATH) -> dict[str, Any]:
    """Parse the current config.yaml into the ``user_preferences`` row shape.

    Used to seed the GET /api/preferences response when no DB row exists yet.
    """
    with open(path, encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)

    search = cfg.get("search", {})
    scoring = cfg.get("scoring", {})
    exclusions = cfg.get("exclusions", {})

    return {
        "search_terms": search.get("search_terms", []),
        "role_families": [],  # config.yaml doesn't store role families; default empty
        "location": search.get("location", "London, UK"),
        "country_indeed": search.get("country_indeed", "UK"),
        "results_wanted": search.get("results_wanted", 30),
        "hours_old": search.get("hours_old", 25),
        "salary_floor": scoring.get("salary_floor", 40000),
        "currency": scoring.get("currency", "GBP"),
        "excluded_title_keywords": exclusions.get("title_keywords", []),
        "excluded_desc_keywords": exclusions.get("description_keywords", []),
    }
