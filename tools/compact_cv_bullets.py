"""Deterministically compact CV bullets for layout retries."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from cv_apply_contract import normalise_keyword_target, target_in_text


FILLER_PATTERNS = [
    (r"\bin order to\b", "to"),
    (r"\bacross sprint cycles\b", ""),
    (r"\bacross sprint\b", ""),
    (r"\bin both on-site and cloud\b", "on-site and cloud"),
    (r"\bsuccessfully\b", ""),
    (r"\beffectively\b", ""),
    (r"\bhighly\b", ""),
    (r"\bclosely\b", ""),
    (r"\bcloser\b", ""),
    (r"\bthat were\b", "that"),
    (r"\bthat was\b", "that"),
    (r"\bthe\b", "the"),
]

LOW_VALUE_WORDS = {
    "across",
    "various",
    "multiple",
    "closely",
    "effectively",
    "successfully",
    "highly",
    "robust",
    "seamless",
    "advanced",
    "comprehensive",
    "scalable",
    "core",
    "key",
    "critical",
    "roadmap",
    "sprint",
    "cycles",
}


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _slot_key(item: dict[str, Any]) -> tuple[str, str, int]:
    return str(item.get("section", "")), str(item.get("subsection", "")), int(item.get("slot_index", 0))


def _keyword_target_map(slot_plan: dict[str, Any]) -> dict[tuple[str, str, int], str]:
    out: dict[tuple[str, str, int], str] = {}
    for card in slot_plan.get("bullet_intent_cards", []):
        target = normalise_keyword_target(card.get("keyword_target", ""))
        if target:
            out[_slot_key(card)] = target
    return out


def _clean_text(text: str) -> str:
    t = re.sub(r"\s+", " ", str(text or "").strip())
    for pattern, replacement in FILLER_PATTERNS:
        t = re.sub(pattern, replacement, t, flags=re.IGNORECASE)
    t = re.sub(r"\s+([.,])", r"\1", t)
    t = re.sub(r"\s+", " ", t).strip(" ,")
    return t


def _locked_indexes(tokens: list[str], target: str) -> set[int]:
    if not target:
        return set()
    target_tokens = target.lower().split()
    if not target_tokens:
        return set()
    lower_tokens = [tok.lower() for tok in tokens]
    for i in range(0, len(tokens) - len(target_tokens) + 1):
        if lower_tokens[i : i + len(target_tokens)] == target_tokens:
            return set(range(i, i + len(target_tokens)))
    return set()


def _token_remove(tokens: list[str], locked: set[int], max_len: int) -> list[str]:
    if len(" ".join(tokens)) <= max_len:
        return tokens

    while len(" ".join(tokens)) > max_len:
        removable = [
            idx
            for idx, tok in enumerate(tokens)
            if idx not in locked and tok.lower().strip(".,") in LOW_VALUE_WORDS
        ]
        if removable:
            tokens.pop(removable[-1])
            locked = {i - 1 if i > removable[-1] else i for i in locked if i != removable[-1]}
            continue

        fallback = [idx for idx in range(len(tokens) - 1, -1, -1) if idx not in locked]
        if not fallback:
            break
        tokens.pop(fallback[0])
        locked = {i - 1 if i > fallback[0] else i for i in locked if i != fallback[0]}

    return tokens


def _ensure_target(text: str, target: str, max_len: int) -> str:
    if not target or target_in_text(target, text):
        return text
    target = target.strip()
    if len(target) >= max_len:
        return text
    candidate = f"{text} {target}".strip()
    if len(candidate) <= max_len:
        return candidate

    words = text.split()
    while words and len(" ".join(words + [target])) > max_len:
        words.pop(0)
    patched = " ".join(words + [target]).strip()
    return patched if patched else text


def compact_text(text: str, target: str, max_len: int) -> str:
    original = re.sub(r"\s+", " ", str(text or "").strip())
    cleaned = _clean_text(original)
    if len(cleaned) <= max_len:
        return _ensure_target(cleaned, target, max_len)

    tokens = cleaned.split()
    locked = _locked_indexes(tokens, target)
    compacted = " ".join(_token_remove(tokens, locked, max_len)).strip(" ,")

    if len(compacted) > max_len:
        compacted = compacted[:max_len].rsplit(" ", 1)[0].strip(" ,")
    compacted = _ensure_target(compacted, target, max_len)

    if target and target_in_text(target, original) and not target_in_text(target, compacted):
        return original
    return compacted or original


def compact_cv_bullets(
    selections: dict[str, Any],
    slot_plan: dict[str, Any],
    max_len: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    updated = json.loads(json.dumps(selections))
    targets = _keyword_target_map(slot_plan)

    changed: list[dict[str, Any]] = []
    for bullet in updated.get("approved_bullets", []):
        key = _slot_key(bullet)
        text = str(bullet.get("text", ""))
        target = targets.get(key, "")
        new_text = compact_text(text=text, target=target, max_len=max_len)
        if new_text != text:
            bullet["text"] = new_text
            changed.append(
                {
                    "slot": [key[0], key[1], key[2]],
                    "before_len": len(text),
                    "after_len": len(new_text),
                    "target_preserved": (not target) or target_in_text(target, new_text),
                }
            )

    report = {
        "changed": len(changed) > 0,
        "changed_count": len(changed),
        "max_len": max_len,
        "changes": changed,
    }
    return updated, report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compact CV bullets deterministically")
    parser.add_argument("--selections", required=True, help="Path to selections JSON")
    parser.add_argument("--slot-plan", required=True, help="Path to slot plan JSON")
    parser.add_argument("--out", required=True, help="Output path for compacted selections")
    parser.add_argument("--max-len", required=True, type=int, help="Maximum bullet length")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    selections = _load(Path(args.selections))
    slot_plan = _load(Path(args.slot_plan))
    compacted, report = compact_cv_bullets(
        selections=selections,
        slot_plan=slot_plan,
        max_len=int(args.max_len),
    )
    _write(Path(args.out), compacted)
    print(json.dumps({"out": args.out, "report": report}, ensure_ascii=False))


if __name__ == "__main__":
    main()
