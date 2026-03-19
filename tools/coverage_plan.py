"""Coverage-first slot assignment for /cv-apply.

Assigns each bullet slot to explicit/implicit coverage mode and chooses
keyword targets for explicit slots before drafting.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any

from cv_apply_contract import BULLET_POLICY, normalise_keyword_target, target_in_text


WORD_RE = re.compile(r"[a-z0-9\+\#\.-]+")


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip().lower())


def _tokens(text: str) -> set[str]:
    return set(WORD_RE.findall(_norm(text)))


def _dedupe_keep_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        cleaned = normalise_keyword_target(value)
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        out.append(cleaned)
    return out


def _variant_bias(cv_variant_id: str, term: str, intent_id: str) -> int:
    digest = hashlib.sha256(f"{cv_variant_id}:{term}:{intent_id}".encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def _extract_terms(jd_keywords: dict[str, Any]) -> tuple[list[str], list[str]]:
    source = jd_keywords.get("keywords", jd_keywords) if isinstance(jd_keywords, dict) else {}
    required = [str(v) for v in source.get("required", [])]
    nice = [str(v) for v in source.get("nice_to_have", [])]

    phrase_inventory = source.get("phrase_inventory", {}) if isinstance(source, dict) else {}
    required += [str(v) for v in phrase_inventory.get("required_phrases", [])]
    nice += [str(v) for v in phrase_inventory.get("nice_to_have_phrases", [])]
    nice += [str(v) for v in phrase_inventory.get("day_to_day_phrases", [])]
    nice += [str(v) for v in phrase_inventory.get("responsibility_phrases", [])]

    return _dedupe_keep_order(required), _dedupe_keep_order(nice)


def _card_blob(card: dict[str, Any], brief_lookup: dict[str, dict[str, Any]]) -> str:
    brief = brief_lookup.get(str(card.get("intent_id", "")), {})
    primary = str(brief.get("primary_claim", {}).get("text", ""))
    secondary = " ".join(str(v) for v in brief.get("secondary_claims", []) if str(v).strip())
    must_include = " ".join(str(v) for v in card.get("must_include", []) if str(v).strip())
    return _norm(" ".join([primary, secondary, must_include]).strip())


def _score_term_for_card(
    term: str,
    card: dict[str, Any],
    blob: str,
    cv_variant_id: str,
) -> int:
    if not blob:
        return 0
    term_norm = normalise_keyword_target(term)
    if not term_norm:
        return 0

    score = 0
    if target_in_text(term_norm, blob):
        score += 100
    else:
        term_tokens = _tokens(term_norm)
        blob_tokens = _tokens(blob)
        if term_tokens and term_tokens.issubset(blob_tokens):
            score += 70
        elif len(term_tokens & blob_tokens) >= max(1, len(term_tokens) - 1):
            score += 30
        else:
            return 0

    existing = normalise_keyword_target(str(card.get("keyword_target", "")))
    if existing == term_norm:
        score += 20
    score += _variant_bias(cv_variant_id, term_norm, str(card.get("intent_id", ""))) % 11
    return score


def _top_support_cards(
    term: str,
    cards: list[dict[str, Any]],
    blob_by_intent: dict[str, str],
    cv_variant_id: str,
    limit: int = 3,
) -> list[dict[str, Any]]:
    ranked: list[tuple[int, dict[str, Any]]] = []
    for card in cards:
        intent_id = str(card.get("intent_id", ""))
        score = _score_term_for_card(term, card, blob_by_intent.get(intent_id, ""), cv_variant_id)
        if score <= 0:
            continue
        ranked.append((score, card))
    ranked.sort(key=lambda item: item[0], reverse=True)
    out: list[dict[str, Any]] = []
    for score, card in ranked[:limit]:
        out.append(
            {
                "intent_id": card.get("intent_id"),
                "slot": [card.get("section"), card.get("subsection"), card.get("slot_index")],
                "score": score,
            }
        )
    return out


def build_coverage_plan(
    slot_plan: dict[str, Any],
    jd_keywords: dict[str, Any],
    explicit_ratio: float = float(BULLET_POLICY["explicit_coverage_ratio"]),
    cv_variant_id: str = "",
) -> tuple[dict[str, Any], dict[str, Any]]:
    updated = json.loads(json.dumps(slot_plan))
    cards = list(updated.get("bullet_intent_cards", []))
    brief_cards = list(updated.get("writer_brief_cards", []))
    brief_lookup = {str(item.get("intent_id", "")): item for item in brief_cards}

    required_terms, nice_terms = _extract_terms(jd_keywords)
    total_slots = len(cards)
    required_explicit = int(math.ceil(total_slots * explicit_ratio)) if total_slots else 0

    blob_by_intent = {
        str(card.get("intent_id", "")): _card_blob(card, brief_lookup)
        for card in cards
    }

    assignments: dict[str, dict[str, str]] = {}
    used_intents: set[str] = set()

    def assign_terms(term_list: list[str], term_type: str, stop_at: int | None = None) -> None:
        for term in term_list:
            if stop_at is not None and len(assignments) >= stop_at:
                return
            candidates: list[tuple[int, dict[str, Any]]] = []
            for card in cards:
                intent_id = str(card.get("intent_id", ""))
                if intent_id in used_intents:
                    continue
                score = _score_term_for_card(term, card, blob_by_intent.get(intent_id, ""), cv_variant_id)
                if score <= 0:
                    continue
                candidates.append((score, card))
            if not candidates:
                continue
            candidates.sort(key=lambda item: item[0], reverse=True)
            best = candidates[0][1]
            intent_id = str(best.get("intent_id", ""))
            assignments[intent_id] = {
                "keyword_target": normalise_keyword_target(term),
                "coverage_mode": "explicit",
                "term_type": term_type,
            }
            used_intents.add(intent_id)

    assign_terms(required_terms, "required")
    assign_terms(nice_terms, "nice_to_have", stop_at=required_explicit)

    if len(assignments) < required_explicit:
        fill_candidates: list[tuple[int, str, dict[str, Any]]] = []
        all_terms = required_terms + [t for t in nice_terms if t not in required_terms]
        for card in cards:
            intent_id = str(card.get("intent_id", ""))
            if intent_id in used_intents:
                continue
            best_term = ""
            best_score = 0
            for term in all_terms:
                score = _score_term_for_card(term, card, blob_by_intent.get(intent_id, ""), cv_variant_id)
                if score > best_score:
                    best_score = score
                    best_term = term
            if best_score > 0 and best_term:
                fill_candidates.append((best_score, best_term, card))
        fill_candidates.sort(key=lambda item: item[0], reverse=True)
        for _, term, card in fill_candidates:
            if len(assignments) >= required_explicit:
                break
            intent_id = str(card.get("intent_id", ""))
            assignments[intent_id] = {
                "keyword_target": normalise_keyword_target(term),
                "coverage_mode": "explicit",
                "term_type": "fill",
            }
            used_intents.add(intent_id)

    for card in cards:
        intent_id = str(card.get("intent_id", ""))
        assignment = assignments.get(intent_id)
        if assignment:
            card["coverage_mode"] = "explicit"
            card["keyword_target"] = assignment["keyword_target"]
            card["keyword_target_norm"] = assignment["keyword_target"]
            card["keyword_target_source"] = f"coverage_plan_{assignment['term_type']}"
        else:
            card["coverage_mode"] = "implicit"
            card["keyword_target"] = ""
            card["keyword_target_norm"] = ""
            card["keyword_target_source"] = "coverage_plan_implicit"

    for brief in brief_cards:
        intent_id = str(brief.get("intent_id", ""))
        assignment = assignments.get(intent_id)
        if assignment:
            brief["coverage_mode"] = "explicit"
            brief["keyword_target"] = assignment["keyword_target"]
            brief["keyword_target_norm"] = assignment["keyword_target"]
            brief["keyword_target_source"] = f"coverage_plan_{assignment['term_type']}"
        else:
            brief["coverage_mode"] = "implicit"
            brief["keyword_target"] = ""
            brief["keyword_target_norm"] = ""
            brief["keyword_target_source"] = "coverage_plan_implicit"

    assigned_targets = [v["keyword_target"] for v in assignments.values() if v.get("keyword_target")]
    assigned_set = set(assigned_targets)
    uncovered_required = [term for term in required_terms if term not in assigned_set]
    uncovered_nice = [term for term in nice_terms if term not in assigned_set]

    uncovered_support = {
        "required": [
            {
                "term": term,
                "support_cards": _top_support_cards(term, cards, blob_by_intent, cv_variant_id),
            }
            for term in uncovered_required
        ],
        "nice_to_have": [
            {
                "term": term,
                "support_cards": _top_support_cards(term, cards, blob_by_intent, cv_variant_id),
            }
            for term in uncovered_nice
        ],
    }

    coverage_report = {
        "total_slots": total_slots,
        "required_explicit_slots": required_explicit,
        "actual_explicit_slots": len(assignments),
        "explicit_quota_met": len(assignments) >= required_explicit,
        "required_terms_total": len(required_terms),
        "required_terms_covered": len(required_terms) - len(uncovered_required),
        "nice_to_have_terms_total": len(nice_terms),
        "nice_to_have_terms_covered": len(nice_terms) - len(uncovered_nice),
        "uncovered_required": uncovered_required,
        "uncovered_nice_to_have": uncovered_nice,
        "uncovered_support": uncovered_support,
        "review_required": bool(uncovered_required or uncovered_nice),
    }

    updated["coverage_policy"] = {
        "explicit_ratio": explicit_ratio,
        "required_explicit_slots": required_explicit,
    }
    updated["coverage_report"] = coverage_report
    return updated, coverage_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build explicit/implicit slot coverage plan", allow_abbrev=False)
    parser.add_argument("--slot-plan", required=True, help="Path to slot plan JSON")
    parser.add_argument("--jd-keywords", required=True, help="Path to extracted JD keywords JSON")
    parser.add_argument("--out", required=True, help="Output path for updated slot plan JSON")
    parser.add_argument("--report-out", help="Optional path for standalone coverage report JSON")
    parser.add_argument("--explicit-ratio", type=float, default=float(BULLET_POLICY["explicit_coverage_ratio"]))
    parser.add_argument("--cv-variant-id", default="", help="Optional stable variant id for deterministic tie-breaks")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    slot_plan = _load(Path(args.slot_plan))
    jd_keywords = _load(Path(args.jd_keywords))
    updated_slot_plan, coverage_report = build_coverage_plan(
        slot_plan=slot_plan,
        jd_keywords=jd_keywords,
        explicit_ratio=float(args.explicit_ratio),
        cv_variant_id=str(args.cv_variant_id or ""),
    )
    _write(Path(args.out), updated_slot_plan)
    if args.report_out:
        _write(Path(args.report_out), coverage_report)
    print(json.dumps({"out": str(args.out), "coverage_report": coverage_report}, ensure_ascii=False))


if __name__ == "__main__":
    main()
