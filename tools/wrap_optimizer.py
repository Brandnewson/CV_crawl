"""Wrap-aware CV bullet detection and rephrase optimization.

No brute-force truncation: all edits are phrase-level rewrites while preserving
keyword targets and provenance bindings.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import fitz

from cv_apply_contract import BULLET_POLICY, normalise_keyword_target, target_in_text


WORD_RE = re.compile(r"[a-z0-9\+\#\.-]+")
MULTISPACE_RE = re.compile(r"\s+")

REPHRASE_PATTERNS = [
    (r"\bin order to\b", "to"),
    (r"\bas part of\b", "for"),
    (r"\bwith the aim of\b", "to"),
    (r"\bsuccessfully\b", ""),
    (r"\beffectively\b", ""),
    (r"\bclosely\b", ""),
    (r"\bhighly\b", ""),
    (r"\bmultiple\b", ""),
    (r"\bvarious\b", ""),
    (r"\bthat were\b", "that"),
    (r"\bthat was\b", "that"),
    (r"\butilised\b", "used"),
    (r"\butilized\b", "used"),
    (r"\bimplemented\b", "built"),
    (r"\bcollaborated with\b", "partnered with"),
]

LONG_WORD_REWRITES = {
    "optimisation": "optimization",
    "optimised": "optimized",
    "modelling": "modeling",
    "coordinated": "led",
    "configuration": "config",
    "integration": "integrating",
    "performance": "speed",
}

FILLER_WORDS = {
    "very",
    "robust",
    "seamless",
    "comprehensive",
    "critical",
    "significant",
}


def _load(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _slot_key(item: dict[str, Any]) -> tuple[str, str, int]:
    return str(item.get("section", "")), str(item.get("subsection", "")), int(item.get("slot_index", 0))


def _norm(text: str) -> str:
    return MULTISPACE_RE.sub(" ", str(text or "").strip().lower())


def _tokenize(text: str) -> list[str]:
    return WORD_RE.findall(_norm(text))


def _extract_pdf_words(pdf_path: Path) -> list[list[dict[str, Any]]]:
    pages: list[list[dict[str, Any]]] = []
    doc = fitz.open(str(pdf_path))
    try:
        for page in doc:
            words = page.get_text("words")
            words_sorted = sorted(words, key=lambda w: (int(w[5]), int(w[6]), int(w[7])))
            page_words: list[dict[str, Any]] = []
            for item in words_sorted:
                token = _norm(str(item[4]))
                norm_token = WORD_RE.findall(token)
                if not norm_token:
                    continue
                page_words.append(
                    {
                        "token": norm_token[0],
                        "block": int(item[5]),
                        "line": int(item[6]),
                        "word": int(item[7]),
                    }
                )
            pages.append(page_words)
    finally:
        doc.close()
    return pages


def _best_match_for_tokens(page_words: list[dict[str, Any]], tokens: list[str]) -> tuple[float, set[tuple[int, int]]]:
    if not page_words or not tokens:
        return 0.0, set()

    best_ratio = 0.0
    best_lines: set[tuple[int, int]] = set()
    starts = [idx for idx, item in enumerate(page_words) if item["token"] == tokens[0]]
    if not starts:
        return 0.0, set()

    for start in starts:
        t_idx = 0
        p_idx = start
        matched_lines: set[tuple[int, int]] = set()
        misses = 0
        while p_idx < len(page_words) and t_idx < len(tokens):
            if page_words[p_idx]["token"] == tokens[t_idx]:
                matched_lines.add((page_words[p_idx]["block"], page_words[p_idx]["line"]))
                t_idx += 1
                misses = 0
            else:
                misses += 1
                if misses > 16:
                    break
            p_idx += 1
        ratio = t_idx / max(1, len(tokens))
        if ratio > best_ratio:
            best_ratio = ratio
            best_lines = matched_lines
        if ratio >= 0.95:
            break
    return best_ratio, best_lines


def detect_wrapped_bullets(
    pdf_path: Path,
    selections: dict[str, Any],
    min_match_ratio: float = 0.62,
) -> dict[str, Any]:
    pages = _extract_pdf_words(pdf_path)
    wrapped: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []

    for bullet in selections.get("approved_bullets", []):
        tokens = _tokenize(str(bullet.get("text", "")))
        if len(tokens) < 3:
            continue
        best_ratio = 0.0
        best_page = -1
        best_line_count = 0
        for page_index, page_words in enumerate(pages):
            ratio, lines = _best_match_for_tokens(page_words, tokens)
            if ratio > best_ratio:
                best_ratio = ratio
                best_page = page_index
                best_line_count = len(lines)
        payload = {
            "slot": [bullet.get("section"), bullet.get("subsection"), bullet.get("slot_index")],
            "intent_id": bullet.get("intent_id"),
            "text": bullet.get("text", ""),
            "match_ratio": round(best_ratio, 3),
            "page_index": best_page,
            "line_count": best_line_count,
        }
        if best_ratio < min_match_ratio:
            unresolved.append(payload)
            continue
        if best_line_count > 1:
            wrapped.append(payload)

    return {
        "wrapped_bullets": wrapped,
        "wrapped_count": len(wrapped),
        "unresolved_bullets": unresolved,
        "unresolved_count": len(unresolved),
    }


def _apply_phrase_rewrites(text: str) -> str:
    updated = text
    for pattern, replacement in REPHRASE_PATTERNS:
        updated = re.sub(pattern, replacement, updated, flags=re.IGNORECASE)
    return MULTISPACE_RE.sub(" ", updated).strip(" ,")


def _apply_word_rewrites(text: str) -> str:
    words = text.split()
    rewritten: list[str] = []
    for raw in words:
        lower = raw.lower().strip(".,")
        core = LONG_WORD_REWRITES.get(lower, lower)
        if core in FILLER_WORDS:
            continue
        suffix = ""
        if raw.endswith((".", ",")):
            suffix = raw[-1]
        rewritten.append(core + suffix)
    return MULTISPACE_RE.sub(" ", " ".join(rewritten)).strip(" ,")


def rephrase_bullet_text(
    text: str,
    target: str,
    preferred_target_chars: int = int(BULLET_POLICY["preferred_target_chars"]),
) -> tuple[str, dict[str, Any]]:
    original = MULTISPACE_RE.sub(" ", str(text or "").strip())
    target_norm = normalise_keyword_target(target)
    updated = original
    changed_steps: list[str] = []

    step1 = _apply_phrase_rewrites(updated)
    if step1 != updated:
        updated = step1
        changed_steps.append("phrase_rewrites")

    step2 = _apply_word_rewrites(updated)
    if step2 != updated:
        updated = step2
        changed_steps.append("word_rewrites")

    if len(updated) > preferred_target_chars and "," in updated:
        left, right = updated.rsplit(",", 1)
        if not target_norm or target_in_text(target_norm, left):
            updated = left.strip()
            changed_steps.append("trim_trailing_clause")

    if target_norm and target_in_text(target_norm, original) and not target_in_text(target_norm, updated):
        return original, {
            "changed": False,
            "reason": "target_preservation_guard",
            "before_len": len(original),
            "after_len": len(original),
            "steps": [],
        }

    updated = MULTISPACE_RE.sub(" ", updated).strip(" ,")
    if not updated:
        updated = original

    return updated, {
        "changed": updated != original,
        "before_len": len(original),
        "after_len": len(updated),
        "steps": changed_steps,
    }


def rephrase_wrapped_bullets(
    selections: dict[str, Any],
    slot_plan: dict[str, Any],
    wrapped_bullets: list[dict[str, Any]],
    preferred_target_chars: int = int(BULLET_POLICY["preferred_target_chars"]),
) -> tuple[dict[str, Any], dict[str, Any]]:
    updated = json.loads(json.dumps(selections))
    wrapped_keys = {
        (str(item["slot"][0]), str(item["slot"][1]), int(item["slot"][2]))
        for item in wrapped_bullets
    }
    target_by_slot = {
        _slot_key(card): normalise_keyword_target(str(card.get("keyword_target", "")))
        for card in slot_plan.get("bullet_intent_cards", [])
    }

    changes: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    for bullet in updated.get("approved_bullets", []):
        key = _slot_key(bullet)
        if key not in wrapped_keys:
            continue
        target = target_by_slot.get(key, "")
        new_text, meta = rephrase_bullet_text(
            text=str(bullet.get("text", "")),
            target=target,
            preferred_target_chars=preferred_target_chars,
        )
        if meta["changed"]:
            bullet["text"] = new_text
            bullet["source"] = "rephrasing"
            bullet["rephrase_generation"] = int(bullet.get("rephrase_generation", 0)) + 1
            changes.append(
                {
                    "slot": [key[0], key[1], key[2]],
                    "before_len": meta["before_len"],
                    "after_len": meta["after_len"],
                    "steps": meta["steps"],
                    "target_preserved": (not target) or target_in_text(target, new_text),
                }
            )
        else:
            unresolved.append(
                {
                    "slot": [key[0], key[1], key[2]],
                    "reason": meta.get("reason", "no_effective_rephrase"),
                    "length": len(str(bullet.get("text", ""))),
                }
            )

    report = {
        "changed": bool(changes),
        "changed_count": len(changes),
        "unresolved_count": len(unresolved),
        "changes": changes,
        "unresolved": unresolved,
    }
    return updated, report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Detect and rephrase wrapped CV bullets", allow_abbrev=False)
    parser.add_argument("--pdf", required=True, help="Rendered CV PDF path")
    parser.add_argument("--selections", required=True, help="Selections JSON path")
    parser.add_argument("--slot-plan", required=True, help="Slot plan JSON path")
    parser.add_argument("--out", required=True, help="Output path for updated selections")
    parser.add_argument("--preferred-target-chars", type=int, default=int(BULLET_POLICY["preferred_target_chars"]))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    selections = _load(Path(args.selections), default={})
    slot_plan = _load(Path(args.slot_plan), default={})
    wrap_report = detect_wrapped_bullets(Path(args.pdf), selections)
    updated, rephrase_report = rephrase_wrapped_bullets(
        selections=selections,
        slot_plan=slot_plan,
        wrapped_bullets=wrap_report.get("wrapped_bullets", []),
        preferred_target_chars=int(args.preferred_target_chars),
    )
    _write(Path(args.out), updated)
    print(
        json.dumps(
            {
                "wrap_report": wrap_report,
                "rephrase_report": rephrase_report,
                "out": str(args.out),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
