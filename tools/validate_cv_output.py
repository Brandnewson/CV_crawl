"""Canonical deterministic validator for /cv-apply draft selections."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from cv_apply_contract import normalise_keyword_target, target_in_text
from validate_redundancy import validate_redundancy


HARD_MIN_LEN = 80
HARD_MAX_LEN = 120
BANNED_PHRASES = (
    "fast-paced",
    "passionate about",
    "team player",
    "leveraged synergies",
    "results-driven",
    "dynamic team",
)


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _explicit_not_terms(work_exp: dict[str, Any]) -> dict[str, list[str]]:
    terms: dict[str, list[str]] = {}
    for role in work_exp.get("work_experience", []):
        org = role.get("org", "")
        org_terms = []
        for item in role.get("explicit_not", []):
            t = _norm(str(item))
            if t:
                org_terms.append(t)
        terms[org] = org_terms
    return terms


def _required_slot_keys(slot_plan: dict[str, Any]) -> set[tuple[str, str, int]]:
    keys: set[tuple[str, str, int]] = set()
    for card in slot_plan.get("bullet_intent_cards", []):
        keys.add((card["section"], card["subsection"], int(card["slot_index"])))
    return keys


def _selection_slot_keys(selections: dict[str, Any]) -> set[tuple[str, str, int]]:
    keys: set[tuple[str, str, int]] = set()
    for bullet in selections.get("approved_bullets", []):
        keys.add((bullet.get("section", ""), bullet.get("subsection", ""), int(bullet.get("slot_index", 0))))
    return keys


def _keyword_target_by_slot(slot_plan: dict[str, Any]) -> dict[tuple[str, str, int], str]:
    targets: dict[tuple[str, str, int], str] = {}
    for card in slot_plan.get("bullet_intent_cards", []):
        keyword_target = normalise_keyword_target(str(card.get("keyword_target", "")))
        if not keyword_target:
            continue
        key = (str(card.get("section", "")), str(card.get("subsection", "")), int(card.get("slot_index", 0)))
        targets[key] = keyword_target
    return targets


def _coverage_mode_by_slot(slot_plan: dict[str, Any]) -> dict[tuple[str, str, int], str]:
    modes: dict[tuple[str, str, int], str] = {}
    for card in slot_plan.get("bullet_intent_cards", []):
        key = (str(card.get("section", "")), str(card.get("subsection", "")), int(card.get("slot_index", 0)))
        modes[key] = str(card.get("coverage_mode", "implicit")).strip().lower() or "implicit"
    return modes


def validate(
    selections: dict[str, Any],
    slot_plan: dict[str, Any],
    work_exp: dict[str, Any] | None = None,
    length_limits: dict[str, int] | None = None,
) -> dict[str, Any]:
    hard_failures: list[dict[str, Any]] = []
    soft_warnings: list[dict[str, Any]] = []
    explicit_not = _explicit_not_terms(work_exp or {})
    keyword_targets = _keyword_target_by_slot(slot_plan)
    coverage_modes = _coverage_mode_by_slot(slot_plan)
    min_len = int((length_limits or {}).get("min", HARD_MIN_LEN))
    max_len = int((length_limits or {}).get("hard_max", HARD_MAX_LEN))
    target_len = int((length_limits or {}).get("target", 110))
    explicit_ratio = float(slot_plan.get("coverage_policy", {}).get("explicit_ratio", 0.5))

    required_keys = _required_slot_keys(slot_plan)
    actual_keys = _selection_slot_keys(selections)
    missing_slots = sorted(required_keys - actual_keys)
    extra_slots = sorted(actual_keys - required_keys)
    if missing_slots:
        hard_failures.append({"type": "slot_fill_missing", "missing_slots": missing_slots})
    if extra_slots:
        hard_failures.append({"type": "slot_fill_extra", "extra_slots": extra_slots})

    explicit_slot_keys = {
        key for key, mode in coverage_modes.items() if mode == "explicit"
    }
    required_explicit = int(math.ceil(len(required_keys) * explicit_ratio)) if required_keys else 0
    if len(explicit_slot_keys) < required_explicit:
        hard_failures.append(
            {
                "type": "explicit_quota",
                "required_explicit_slots": required_explicit,
                "actual_explicit_slots": len(explicit_slot_keys),
                "explicit_ratio": explicit_ratio,
            }
        )

    verbs: list[str] = []
    for bullet in selections.get("approved_bullets", []):
        text = str(bullet.get("text", ""))
        slot_key = (bullet.get("section", ""), bullet.get("subsection", ""), int(bullet.get("slot_index", 0)))
        length = len(text)
        if length < min_len or length > max_len:
            hard_failures.append(
                {
                    "type": "length",
                    "slot": [bullet.get("section"), bullet.get("subsection"), bullet.get("slot_index")],
                    "length": length,
                    "min_len": min_len,
                    "max_len": max_len,
                    "text": text,
                }
            )
        elif length > target_len:
            soft_warnings.append(
                {
                    "type": "over_target_length",
                    "slot": [bullet.get("section"), bullet.get("subsection"), bullet.get("slot_index")],
                    "length": length,
                    "target_len": target_len,
                }
            )

        if "intent_id" not in bullet or "provenance" not in bullet:
            hard_failures.append(
                {
                    "type": "schema_provenance",
                    "slot": [bullet.get("section"), bullet.get("subsection"), bullet.get("slot_index")],
                    "reason": "missing intent_id or provenance",
                }
            )

        lowered = _norm(text)
        keyword_target = keyword_targets.get(slot_key, "")
        coverage_mode = coverage_modes.get(slot_key, "implicit")
        if coverage_mode == "explicit" and not keyword_target:
            hard_failures.append(
                {
                    "type": "explicit_slot_missing_target",
                    "slot": [bullet.get("section"), bullet.get("subsection"), bullet.get("slot_index")],
                }
            )
        if coverage_mode == "explicit" and keyword_target and not target_in_text(keyword_target, text):
            hard_failures.append(
                {
                    "type": "keyword_target_verbatim_missing",
                    "slot": [bullet.get("section"), bullet.get("subsection"), bullet.get("slot_index")],
                    "keyword_target": keyword_target,
                    "match_type": "case_insensitive_literal_phrase",
                }
            )
        for phrase in BANNED_PHRASES:
            if phrase in lowered:
                hard_failures.append(
                    {
                        "type": "banned_phrase",
                        "slot": [bullet.get("section"), bullet.get("subsection"), bullet.get("slot_index")],
                        "phrase": phrase,
                    }
                )

        first_word = text.split()[0].lower() if text.split() else ""
        if first_word:
            verbs.append(first_word)

        if bullet.get("section") == "work_experience":
            sub = bullet.get("subsection", "")
            not_terms = explicit_not.get(sub, [])
            for term in not_terms:
                if term and term in lowered:
                    hard_failures.append(
                        {
                            "type": "explicit_not_conflict",
                            "slot": [bullet.get("section"), bullet.get("subsection"), bullet.get("slot_index")],
                            "term": term,
                        }
                    )

    verb_counts = Counter(verbs)
    overused = {verb: c for verb, c in verb_counts.items() if c >= 3}
    if overused:
        hard_failures.append({"type": "verb_dedup", "overused_verbs": overused})

    redundancy = validate_redundancy(selections=selections, slot_plan=slot_plan)
    if not redundancy["ok"]:
        hard_failures.append({"type": "redundancy", "report": redundancy})

    report = {
        "ok": len(hard_failures) == 0,
        "hard_failures": hard_failures,
        "soft_warnings": soft_warnings,
    }
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Canonical deterministic validator for CV selections",
        allow_abbrev=False,
    )
    parser.add_argument("--selections", required=True, help="Path to .cv-apply-selections-tmp.json")
    parser.add_argument("--slot-plan", required=True, help="Path to .cv-apply-slot-plan-tmp.json")
    parser.add_argument("--work-exp", help="Optional path to .cv-work-experience.json for explicit_not checks")
    parser.add_argument("--min-len", type=int, default=HARD_MIN_LEN)
    parser.add_argument("--hard-max-len", type=int, default=HARD_MAX_LEN)
    parser.add_argument("--target-len", type=int, default=110)
    parser.add_argument("--fail-on-issues", action="store_true")
    args = parser.parse_args()

    selections = _load(Path(args.selections))
    slot_plan = _load(Path(args.slot_plan))
    work_exp = _load(Path(args.work_exp)) if args.work_exp else None
    report = validate(
        selections=selections,
        slot_plan=slot_plan,
        work_exp=work_exp,
        length_limits={"min": args.min_len, "hard_max": args.hard_max_len, "target": args.target_len},
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if args.fail_on_issues and not report["ok"]:
        sys.exit(2)


if __name__ == "__main__":
    main()
