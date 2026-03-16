"""Validate semantic redundancy in CV bullets.

Deterministic gate that flags bullets with repeated meaning inside a subsection.
Optionally cross-checks intent cards for intent_id and primary_claim uniqueness.
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from cv_apply_contract import normalize_subsection_id

WORD_RE = re.compile(r"[a-z0-9\+\#\.-]+")
STOPWORDS = {
    "a",
    "an",
    "and",
    "the",
    "to",
    "of",
    "for",
    "in",
    "on",
    "with",
    "using",
    "via",
    "by",
    "across",
    "into",
    "from",
    "through",
}
CONCEPT_STOP = STOPWORDS | {
    "built",
    "build",
    "designed",
    "design",
    "developed",
    "develop",
    "implemented",
    "implement",
    "engineered",
    "generated",
    "creating",
    "created",
}


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _tokens(text: str) -> set[str]:
    return {tok for tok in WORD_RE.findall(_norm(text)) if tok not in STOPWORDS}


def _char_ngrams(text: str, n: int = 3) -> set[str]:
    t = _norm(text)
    if len(t) < n:
        return {t} if t else set()
    return {t[i : i + n] for i in range(len(t) - n + 1)}


def _stem(token: str) -> str:
    for suffix in ("ing", "ed", "es", "s"):
        if token.endswith(suffix) and len(token) > len(suffix) + 2:
            return token[: -len(suffix)]
    return token


def _concept_tokens(text: str) -> set[str]:
    concepts: set[str] = set()
    for token in WORD_RE.findall(_norm(text)):
        if token in CONCEPT_STOP:
            continue
        if len(token) <= 3:
            continue
        concepts.add(_stem(token))
    return concepts


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / max(1, len(a | b))


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _slot_key(item: dict[str, Any]) -> tuple[str, str, int]:
    return item["section"], item["subsection"], int(item["slot_index"])


def validate_redundancy(
    selections: dict[str, Any],
    slot_plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    bullets = selections.get("approved_bullets", [])
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for bullet in bullets:
        grouped[(bullet.get("section", ""), bullet.get("subsection", ""))].append(bullet)

    redundant_pairs: list[dict[str, Any]] = []
    failed: dict[tuple[str, str, int], dict[str, Any]] = {}
    for (section, subsection), bucket in grouped.items():
        bucket = sorted(bucket, key=lambda b: int(b.get("slot_index", 0)))
        for i in range(len(bucket)):
            for j in range(i + 1, len(bucket)):
                b1 = bucket[i]
                b2 = bucket[j]
                t1 = b1.get("text", "")
                t2 = b2.get("text", "")
                lex = _jaccard(_tokens(t1), _tokens(t2))
                ngram = _jaccard(_char_ngrams(t1), _char_ngrams(t2))
                sem = difflib.SequenceMatcher(a=_norm(t1), b=_norm(t2)).ratio()
                concept_overlap = len(_concept_tokens(t1) & _concept_tokens(t2))
                semantic_duplicate = (
                    (lex >= 0.55 and (sem >= 0.74 or ngram >= 0.5))
                    or (concept_overlap >= 3 and sem >= 0.3)
                )
                if semantic_duplicate:
                    redundant_pairs.append(
                        {
                            "section": section,
                            "subsection": subsection,
                            "subsection_id": normalize_subsection_id(section, subsection),
                            "slot_a": int(b1.get("slot_index", 0)),
                            "slot_b": int(b2.get("slot_index", 0)),
                            "lexical_jaccard": round(lex, 3),
                            "semantic_ratio": round(sem, 3),
                            "ngram_jaccard": round(ngram, 3),
                            "concept_overlap": concept_overlap,
                            "text_a": t1,
                            "text_b": t2,
                        }
                    )
                    key = _slot_key(b2)
                    failed[key] = {
                        "section": section,
                        "subsection": subsection,
                        "slot_index": int(b2.get("slot_index", 0)),
                        "text": t2,
                        "reason": "semantic_duplicate_within_subsection",
                    }

    intent_conflicts: list[dict[str, Any]] = []
    intent_index: dict[tuple[str, str, int], dict[str, Any]] = {}
    if slot_plan:
        intent_cards = slot_plan.get("bullet_intent_cards", [])
        for card in intent_cards:
            intent_index[(card["section"], card["subsection"], int(card["slot_index"]))] = card

        primary_per_subsection: dict[tuple[str, str], set[str]] = defaultdict(set)
        for card in intent_cards:
            sub_key = (card["section"], card["subsection"])
            primary = card.get("primary_claim_id", "")
            if primary and primary in primary_per_subsection[sub_key]:
                intent_conflicts.append(
                    {
                        "section": card["section"],
                        "subsection": card["subsection"],
                        "intent_id": card.get("intent_id"),
                        "primary_claim_id": primary,
                        "reason": "duplicate_primary_claim_in_intent_cards",
                    }
                )
            primary_per_subsection[sub_key].add(primary)

        for bullet in bullets:
            key = _slot_key(bullet)
            card = intent_index.get(key)
            if not card:
                intent_conflicts.append(
                    {
                        "section": key[0],
                        "subsection": key[1],
                        "slot_index": key[2],
                        "reason": "missing_intent_card_for_bullet",
                    }
                )
                continue
            if "intent_id" not in bullet:
                intent_conflicts.append(
                    {
                        "section": key[0],
                        "subsection": key[1],
                        "slot_index": key[2],
                        "reason": "bullet_missing_intent_id",
                        "expected_intent_id": card.get("intent_id"),
                    }
                )
                failed[key] = {
                    "section": key[0],
                    "subsection": key[1],
                    "slot_index": key[2],
                    "text": bullet.get("text", ""),
                    "reason": "missing_intent_id",
                }
            elif bullet.get("intent_id") != card.get("intent_id"):
                intent_conflicts.append(
                    {
                        "section": key[0],
                        "subsection": key[1],
                        "slot_index": key[2],
                        "reason": "intent_id_mismatch",
                        "expected_intent_id": card.get("intent_id"),
                        "actual_intent_id": bullet.get("intent_id"),
                    }
                )
                failed[key] = {
                    "section": key[0],
                    "subsection": key[1],
                    "slot_index": key[2],
                    "text": bullet.get("text", ""),
                    "reason": "intent_id_mismatch",
                }

    failed_bullets = sorted(failed.values(), key=lambda b: (b["section"], b["subsection"], b["slot_index"]))
    ok = not redundant_pairs and not intent_conflicts
    return {
        "ok": ok,
        "redundant_pairs": redundant_pairs,
        "intent_conflicts": intent_conflicts,
        "failed_bullets": failed_bullets,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate semantic redundancy in approved CV bullets")
    parser.add_argument("--selections", required=True, help="Path to selections JSON")
    parser.add_argument("--slot-plan", help="Optional path to slot plan JSON")
    parser.add_argument("--fail-on-issues", action="store_true", help="Exit code 2 when validation fails")
    args = parser.parse_args()

    selections = _load(Path(args.selections))
    slot_plan = _load(Path(args.slot_plan)) if args.slot_plan else None
    report = validate_redundancy(selections, slot_plan)
    print(json.dumps(report, indent=2, ensure_ascii=False))

    if args.fail_on_issues and not report["ok"]:
        sys.exit(2)


if __name__ == "__main__":
    main()
