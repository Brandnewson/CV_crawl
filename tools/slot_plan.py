"""Build bullet intent cards from evidence packs.

Enforces diversity before drafting:
- no primary claim reuse in a subsection
- no repeated (intent_type + similarity_group) combo
- pairwise overlap guard on planned intents
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from cv_apply_contract import normalize_subsection_id, normalise_keyword_target

WORD_RE = re.compile(r"[a-z0-9\+\#\.-]+")


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _tokens(text: str) -> set[str]:
    return set(WORD_RE.findall(_norm(text)))


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / max(1, len(a | b))


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _safe_id(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def _classify_intent(claim_text: str) -> str:
    lowered = _norm(claim_text)
    if any(k in lowered for k in ("architect", "design", "system design")):
        return "architecture"
    if any(k in lowered for k in ("integrat", "api", "third-party", "websocket", "rest")):
        return "integration"
    if any(k in lowered for k in ("optimis", "improv", "reduce", "saved", "faster")):
        return "optimisation"
    if any(k in lowered for k in ("analys", "model", "simulation")):
        return "analysis"
    if any(k in lowered for k in ("led", "managed", "mentored", "trained")):
        return "leadership"
    if any(k in lowered for k in ("delivered", "deployed", "shipped")):
        return "outcome"
    return "implementation"


def _confidence_weight(confidence: str) -> int:
    c = confidence.lower()
    if c == "high":
        return 3
    if c == "medium":
        return 2
    return 1


def _match_pack_name(needle: str, candidates: list[dict[str, Any]], section: str) -> dict[str, Any] | None:
    needle_n = _norm(needle)
    exact = [p for p in candidates if p["section"] == section and _norm(p["subsection"]) == needle_n]
    if exact:
        return exact[0]

    for pack in candidates:
        if pack["section"] != section:
            continue
        p = _norm(pack["subsection"])
        if needle_n in p or p in needle_n:
            return pack
    return None


def _project_score(pack: dict[str, Any], claim_lookup: dict[str, dict[str, Any]]) -> int:
    score = 0
    claim_ids = pack.get("allowed_fact_ids", pack.get("eligible_claim_ids", []))
    for claim_id in claim_ids:
        claim = claim_lookup[claim_id]
        score += len(claim.get("keyword_links", [])) * 3
        score += len(claim.get("method_tool", []))
        if claim.get("outcome_impact"):
            score += 2
        score += _confidence_weight(claim.get("confidence", "medium"))
    score -= len(pack.get("coverage_gaps", []))
    score -= pack.get("duplicate_pressure", 0)
    return score


def _build_question_bundle(
    section: str,
    subsection: str,
    shortfall: int,
    sample_claim: str,
) -> list[dict[str, str]]:
    sid = _safe_id(f"{section}_{subsection}")
    seed = sample_claim.strip()[:120]
    return [
        {
            "question_id": f"slot_gap_{sid}_outcome",
            "section": section,
            "subsection": subsection,
            "question": f"What measurable outcome resulted from this work: \"{seed}\"?",
            "why_needed": f"Need distinct outcome evidence to fill {shortfall} remaining slot(s) without paraphrase.",
        },
        {
            "question_id": f"slot_gap_{sid}_ownership",
            "section": section,
            "subsection": subsection,
            "question": f"What was your specific ownership boundary for this work: \"{seed}\"?",
            "why_needed": "Need clear ownership evidence to avoid overstated or duplicate intent cards.",
        },
        {
            "question_id": f"slot_gap_{sid}_method",
            "section": section,
            "subsection": subsection,
            "question": "What tool or method differed between the strongest examples in this subsection?",
            "why_needed": "Need method-level contrast to create non-overlapping bullets.",
        },
    ]


def _header_swap_text(pack: dict[str, Any]) -> str:
    title = pack.get("project_title") or pack["subsection"]
    if pack.get("partial_contribution"):
        title = f"{title} (partial contribution)"
    tech = [str(t).strip() for t in pack.get("tech_tags", []) if str(t).strip()]
    if not tech:
        return title
    return f"{title} | {', '.join(tech[:6])}"


def _normalise_keyword_candidates(raw_keyword: str) -> list[str]:
    cleaned = normalise_keyword_target(raw_keyword)
    if not cleaned:
        return []
    # Split compound targets like "rag / vector databases" into distinct options.
    split_terms = re.split(r"\s*(?:/|,|\bor\b|\band\b)\s*", cleaned)
    candidates = []
    for term in split_terms:
        t = normalise_keyword_target(term)
        if not t:
            continue
        if len(t.split()) > 6:
            continue
        candidates.append(t)
    deduped: list[str] = []
    for candidate in candidates:
        if candidate not in deduped:
            deduped.append(candidate)
    return deduped


def _pick_keyword_target(
    claim: dict[str, Any],
    required_keywords: list[str],
) -> tuple[str, str]:
    required_norm = [normalise_keyword_target(k) for k in required_keywords if normalise_keyword_target(k)]
    claim_links = [str(v) for v in claim.get("keyword_links", []) if str(v).strip()]
    expanded: list[str] = []
    for raw in claim_links:
        expanded.extend(_normalise_keyword_candidates(raw))
    if not expanded:
        return "", "none"

    for required in required_norm:
        if required in expanded:
            return required, "required_exact"

    # Prefer a concise single target to avoid impossible verbatim checks.
    for candidate in expanded:
        if "/" in candidate:
            continue
        return candidate, "claim_keyword_first_clean"
    return "", "none"


def _pick_intents_for_subsection(
    section: str,
    subsection: str,
    slot_count: int,
    pack: dict[str, Any],
    claim_lookup: dict[str, dict[str, Any]],
    required_keywords: list[str],
    intent_prefix: str,
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    claims = [claim_lookup[cid] for cid in pack.get("eligible_claim_ids", []) if cid in claim_lookup]
    if not claims:
        claims = [claim_lookup[cid] for cid in pack.get("allowed_fact_ids", []) if cid in claim_lookup]
    claims = sorted(
        claims,
        key=lambda c: (
            len(c.get("keyword_links", [])),
            bool(c.get("outcome_impact")),
            len(c.get("method_tool", [])),
            _confidence_weight(c.get("confidence", "medium")),
        ),
        reverse=True,
    )
    if not claims:
        return [], _build_question_bundle(section, subsection, slot_count, "No eligible evidence")

    used_primary: set[str] = set()
    used_combo: set[tuple[str, str]] = set()
    selected_text_tokens: list[set[str]] = []
    cards: list[dict[str, Any]] = []
    questions: list[dict[str, str]] = []

    for slot_index in range(slot_count):
        chosen: dict[str, Any] | None = None
        chosen_intent = ""
        for claim in claims:
            cid = claim["claim_id"]
            if cid in used_primary:
                continue
            intent_type = _classify_intent(claim["claim_text"])
            combo = (intent_type, claim.get("similarity_group", ""))
            if combo in used_combo:
                continue

            this_tokens = _tokens(claim["claim_text"])
            if any(_jaccard(this_tokens, prior) >= 0.55 for prior in selected_text_tokens):
                continue

            chosen = claim
            chosen_intent = intent_type
            break

        if chosen is None:
            shortfall = slot_count - len(cards)
            sample = claims[0]["claim_text"] if claims else "No evidence available"
            questions.extend(_build_question_bundle(section, subsection, shortfall, sample))
            break

        used_primary.add(chosen["claim_id"])
        used_combo.add((chosen_intent, chosen.get("similarity_group", "")))
        selected_text_tokens.append(_tokens(chosen["claim_text"]))

        secondary_ids = []
        for claim in claims:
            cid = claim["claim_id"]
            if cid == chosen["claim_id"]:
                continue
            if claim.get("similarity_group") == chosen.get("similarity_group"):
                continue
            secondary_ids.append(cid)
            if len(secondary_ids) == 2:
                break

        keyword_target, keyword_target_source = _pick_keyword_target(
            claim=chosen,
            required_keywords=required_keywords,
        )

        must_include = [v for v in [chosen.get("action")] + chosen.get("method_tool", []) if v][:3]
        must_avoid = []
        if pack.get("partial_contribution"):
            must_avoid.extend(["full ownership wording", "solely built end-to-end"])

        cards.append(
            {
                "intent_id": f"{intent_prefix}_{slot_index}",
                "section": section,
                "subsection": subsection,
                "subsection_id": normalize_subsection_id(section, subsection),
                "slot_index": slot_index,
                "intent_type": chosen_intent,
                "primary_claim_id": chosen["claim_id"],
                "secondary_claim_ids": secondary_ids,
                "keyword_target": keyword_target,
                "keyword_target_source": keyword_target_source,
                "must_include": must_include,
                "must_avoid": must_avoid,
            }
        )

    return cards, questions


def build_slot_plan(evidence: dict[str, Any], template_map: dict[str, Any]) -> dict[str, Any]:
    claim_units = evidence.get("claim_units", [])
    claim_lookup = {c["claim_id"]: c for c in claim_units}
    packs = evidence.get("evidence_packs", [])
    required = evidence.get("keywords", {}).get("required", [])

    work_map = template_map.get("work_experience", {})
    project_map = template_map.get("technical_projects", {})

    hidden_projects: list[str] = []
    header_swaps: list[dict[str, Any]] = []
    intent_cards: list[dict[str, Any]] = []
    insufficiency_questions: list[dict[str, str]] = []

    for subsection, meta in work_map.items():
        slot_count = len(meta.get("bullet_xpaths", []))
        pack = _match_pack_name(subsection, packs, "work_experience")
        if pack is None:
            insufficiency_questions.extend(
                _build_question_bundle("work_experience", subsection, slot_count, "No subsection evidence matched")
            )
            continue
        cards, questions = _pick_intents_for_subsection(
            section="work_experience",
            subsection=subsection,
            slot_count=slot_count,
            pack=pack,
            claim_lookup=claim_lookup,
            required_keywords=required,
            intent_prefix=f"intent_work_{_safe_id(subsection)}",
        )
        intent_cards.extend(cards)
        insufficiency_questions.extend(questions)

    project_packs = [p for p in packs if p["section"] == "technical_projects"]
    project_packs = sorted(project_packs, key=lambda p: _project_score(p, claim_lookup), reverse=True)
    template_project_subsections = list(project_map.keys())
    assigned: dict[str, dict[str, Any]] = {}
    for idx, template_subsection in enumerate(template_project_subsections):
        if idx < len(project_packs):
            assigned[template_subsection] = project_packs[idx]
        else:
            hidden_projects.append(template_subsection)

    for header_idx, template_subsection in enumerate(template_project_subsections):
        if template_subsection in hidden_projects:
            continue
        pack = assigned[template_subsection]
        header_swaps.append(
            {
                "section": "technical_projects",
                "subsection": template_subsection,
                "header_xpath_index": 0,
                "text": _header_swap_text(pack),
            }
        )
        slot_count = len(project_map[template_subsection].get("bullet_xpaths", []))
        cards, questions = _pick_intents_for_subsection(
            section="technical_projects",
            subsection=template_subsection,
            slot_count=slot_count,
            pack=pack,
            claim_lookup=claim_lookup,
            required_keywords=required,
            intent_prefix=f"intent_proj_{_safe_id(template_subsection)}",
        )
        intent_cards.extend(cards)
        insufficiency_questions.extend(questions)

    brief_cards = []
    for card in intent_cards:
        primary = claim_lookup.get(card["primary_claim_id"], {})
        secondary = [claim_lookup[cid]["claim_text"] for cid in card.get("secondary_claim_ids", []) if cid in claim_lookup]
        brief_cards.append(
            {
                "intent_id": card["intent_id"],
                "section": card["section"],
                "subsection": card["subsection"],
                "subsection_id": card["subsection_id"],
                "slot_index": card["slot_index"],
                "intent_type": card["intent_type"],
                "keyword_target": card["keyword_target"],
                "keyword_target_source": card.get("keyword_target_source", "none"),
                "primary_claim": {
                    "claim_id": card["primary_claim_id"],
                    "text": primary.get("claim_text", ""),
                    "source_ref": primary.get("source_ref", {}),
                },
                "secondary_claims": secondary,
                "must_include": card.get("must_include", []),
                "must_avoid": card.get("must_avoid", []),
            }
        )

    is_sufficient = len(insufficiency_questions) == 0
    return {
        "schema_version": 1,
        "hidden_projects": hidden_projects,
        "header_swaps": header_swaps,
        "bullet_intent_cards": intent_cards,
        "writer_brief_cards": brief_cards,
        "insufficiency_questions": insufficiency_questions,
        "is_sufficient": is_sufficient,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate slot plan with diversity constraints",
        allow_abbrev=False,
    )
    parser.add_argument("--evidence", required=True, help="Path to evidence_select output JSON")
    parser.add_argument("--template-map", required=True, help="Path to template_map.json")
    parser.add_argument("--out", required=True, help="Output path for slot plan JSON")
    args = parser.parse_args()

    evidence = _load(Path(args.evidence))
    template_map = _load(Path(args.template_map))
    payload = build_slot_plan(evidence, template_map)

    out_path = Path(args.out)
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(str(out_path))


if __name__ == "__main__":
    main()
