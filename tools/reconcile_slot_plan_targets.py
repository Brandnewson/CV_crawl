"""Reconcile slot-plan keyword targets against current bullet text."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from cv_apply_contract import normalise_keyword_target, target_in_text


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _slot_key(item: dict[str, Any]) -> tuple[str, str, int]:
    return str(item.get("section", "")), str(item.get("subsection", "")), int(item.get("slot_index", 0))


def _extract_keywords(raw_keywords: dict[str, Any] | None) -> list[str]:
    if not raw_keywords:
        return []
    root = raw_keywords.get("keywords", raw_keywords)
    out: list[str] = []
    for group in ("required", "nice_to_have"):
        for kw in root.get(group, []):
            normed = normalise_keyword_target(str(kw))
            if normed and normed not in out:
                out.append(normed)
    return out


def _infer_target_from_text(text: str, jd_keywords: list[str]) -> str:
    matches = [kw for kw in jd_keywords if target_in_text(kw, text)]
    if not matches:
        return ""
    # Prefer the most specific phrase.
    return sorted(matches, key=lambda kw: (len(kw.split()), len(kw)), reverse=True)[0]


def reconcile_slot_plan_targets(
    slot_plan: dict[str, Any],
    selections: dict[str, Any],
    raw_keywords: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    bullets_by_slot = {
        _slot_key(item): str(item.get("text", ""))
        for item in selections.get("approved_bullets", [])
    }
    jd_keywords = _extract_keywords(raw_keywords)

    updated = json.loads(json.dumps(slot_plan))
    changes: list[dict[str, Any]] = []

    card_lookup: dict[tuple[str, str, int], dict[str, Any]] = {}
    for card in updated.get("bullet_intent_cards", []):
        key = _slot_key(card)
        card_lookup[key] = card

        old_target = normalise_keyword_target(card.get("keyword_target", ""))
        if not old_target:
            card["keyword_target"] = ""
            continue

        bullet_text = bullets_by_slot.get(key, "")
        if bullet_text and target_in_text(old_target, bullet_text):
            card["keyword_target"] = old_target
            continue

        inferred = _infer_target_from_text(bullet_text, jd_keywords) if bullet_text else ""
        new_target = inferred if inferred and target_in_text(inferred, bullet_text) else ""
        card["keyword_target"] = new_target
        card["keyword_target_source"] = "reconciled_from_bullet" if new_target else "cleared_stale_target"
        changes.append(
            {
                "slot": [key[0], key[1], key[2]],
                "previous_target": old_target,
                "new_target": new_target,
                "reason": "target_not_in_current_bullet",
            }
        )

    # Keep brief cards aligned with canonical cards.
    for brief in updated.get("writer_brief_cards", []):
        key = _slot_key(brief)
        source = card_lookup.get(key)
        if not source:
            continue
        brief["keyword_target"] = source.get("keyword_target", "")
        if "keyword_target_source" in source:
            brief["keyword_target_source"] = source["keyword_target_source"]

    report = {
        "changed": len(changes) > 0,
        "changed_slots": len(changes),
        "changes": changes,
    }
    return updated, report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reconcile stale slot-plan keyword targets")
    parser.add_argument("--slot-plan", required=True, help="Path to slot plan JSON")
    parser.add_argument("--selections", required=True, help="Path to selections JSON")
    parser.add_argument("--out", required=True, help="Output path for reconciled slot plan")
    parser.add_argument("--keywords", help="Optional keywords JSON path")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    slot_plan = _load(Path(args.slot_plan))
    selections = _load(Path(args.selections))
    raw_keywords = _load(Path(args.keywords)) if args.keywords else None
    reconciled, report = reconcile_slot_plan_targets(slot_plan, selections, raw_keywords)
    _write(Path(args.out), reconciled)
    print(json.dumps({"out": args.out, "report": report}, ensure_ascii=False))


if __name__ == "__main__":
    main()
