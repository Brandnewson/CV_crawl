"""Build diversity-first evidence packs for /cv-apply.

This stage converts raw work/project facts into atomic claim units, marks
near-duplicates, and emits subsection evidence packs for slot planning.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

from cv_apply_contract import normalize_subsection_id

WORD_RE = re.compile(r"[a-z0-9\+\#\.-]+")
OUTCOME_RE = re.compile(
    r"(\d+[%xX]?|improv|reduc|increas|saved|enabled|delivered|shipped|adopted|active use|reliab|optimis)",
    re.IGNORECASE,
)
SCALE_RE = re.compile(r"\d")
ACTION_RE = re.compile(r"^[A-Za-z]+")
TECH_HINTS = [
    "python",
    "typescript",
    "react",
    "node.js",
    "node",
    "docker",
    "aws",
    "azure",
    "fastapi",
    "rest",
    "websocket",
    "sql",
    "nosql",
    "ci/cd",
    "ci",
    "cd",
    "atlas",
    "llm",
    "claude",
    "opencv",
    "cnn",
    "matlab",
    "pytorch",
]


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _tokens(text: str) -> set[str]:
    return set(WORD_RE.findall(_norm(text)))


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / max(1, len(a | b))


def _load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _safe_id(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def _extract_method_tools(text: str) -> list[str]:
    lowered = _norm(text)
    found = [hint for hint in TECH_HINTS if hint in lowered]
    return sorted(set(found))


def _extract_action(text: str) -> str:
    m = ACTION_RE.search(text.strip())
    return m.group(0) if m else ""


def _extract_system_component(text: str) -> str:
    cleaned = re.sub(r"[^\w\s/\-]", " ", text).strip()
    words = cleaned.split()
    if len(words) <= 1:
        return cleaned
    return " ".join(words[1:8])


def _extract_outcome(text: str) -> str:
    return text if OUTCOME_RE.search(text) else ""


def _keyword_links(text: str, keywords: dict[str, list[str]]) -> list[str]:
    lowered = _norm(text)
    links: list[str] = []
    for key in keywords.get("required", []) + keywords.get("nice_to_have", []):
        if key and _norm(key) in lowered:
            links.append(key)
    return links


def _confidence_weight(confidence: str) -> int:
    c = confidence.lower()
    if c == "high":
        return 3
    if c == "medium":
        return 2
    return 1


@dataclass
class ClaimUnit:
    claim_id: str
    section: str
    subsection: str
    claim_text: str
    action: str
    system_component: str
    method_tool: list[str]
    outcome_impact: str
    keyword_links: list[str]
    confidence: str
    source_ref: dict[str, Any]
    similarity_group: str = ""
    explicit_not_risk: bool = False
    project_name: str = ""
    project_title: str = ""
    partial_contribution: bool = False


def _build_work_claims(
    work_exp: dict[str, Any],
    keywords: dict[str, list[str]],
) -> list[ClaimUnit]:
    claims: list[ClaimUnit] = []
    for role in work_exp.get("work_experience", []):
        org = role.get("org", "").strip()
        explicit_not = [_norm(v) for v in role.get("explicit_not", [])]
        for idx, fact in enumerate(role.get("verified_facts", [])):
            text = str(fact).strip()
            lowered = _norm(text)
            explicit_risk = any(item and item in lowered for item in explicit_not)
            claims.append(
                ClaimUnit(
                    claim_id=f"work_{_safe_id(org)}_{idx}",
                    section="work_experience",
                    subsection=org,
                    claim_text=text,
                    action=_extract_action(text),
                    system_component=_extract_system_component(text),
                    method_tool=_extract_method_tools(text),
                    outcome_impact=_extract_outcome(text),
                    keyword_links=_keyword_links(text, keywords),
                    confidence="high",
                    source_ref={
                        "source": ".cv-work-experience.json",
                        "org": org,
                        "fact_index": idx,
                        "explicit_not": role.get("explicit_not", []),
                    },
                    explicit_not_risk=explicit_risk,
                )
            )
    return claims


def _build_project_claims(
    store: dict[str, Any],
    keywords: dict[str, list[str]],
    excluded: set[str],
    partial: set[str],
) -> list[ClaimUnit]:
    claims: list[ClaimUnit] = []
    for project in store.get("projects", []):
        project_name = str(project.get("name", "")).strip()
        if project_name in excluded:
            continue
        project_title = str(project.get("title", project_name)).strip()
        is_partial = project_name in partial
        for idx, bullet in enumerate(project.get("bullets", [])):
            text = str(bullet.get("text", "")).strip()
            confidence = str(bullet.get("confidence", "medium"))
            links = bullet.get("keywords_matched") or _keyword_links(text, keywords)
            claims.append(
                ClaimUnit(
                    claim_id=f"proj_{_safe_id(project_name)}_{idx}",
                    section="technical_projects",
                    subsection=project_title,
                    claim_text=text,
                    action=_extract_action(text),
                    system_component=_extract_system_component(text),
                    method_tool=_extract_method_tools(text),
                    outcome_impact=_extract_outcome(text),
                    keyword_links=list(links),
                    confidence=confidence,
                    source_ref={
                        "source": ".cv-harvest-store.json",
                        "project_name": project_name,
                        "project_title": project_title,
                        "bullet_index": idx,
                        "question_id": bullet.get("question_id"),
                    },
                    project_name=project_name,
                    project_title=project_title,
                    partial_contribution=is_partial,
                )
            )
    return claims


def _assign_similarity_groups(claims: list[ClaimUnit]) -> list[dict[str, Any]]:
    by_subsection: dict[tuple[str, str], list[ClaimUnit]] = {}
    for claim in claims:
        by_subsection.setdefault((claim.section, claim.subsection), []).append(claim)

    groups: list[dict[str, Any]] = []
    gid = 1
    for (section, subsection), bucket in by_subsection.items():
        assigned: set[str] = set()
        for claim in bucket:
            if claim.claim_id in assigned:
                continue
            claim_tokens = _tokens(claim.claim_text)
            member_ids = [claim.claim_id]
            assigned.add(claim.claim_id)
            for other in bucket:
                if other.claim_id in assigned:
                    continue
                other_tokens = _tokens(other.claim_text)
                score = _jaccard(claim_tokens, other_tokens)
                if score >= 0.48:
                    member_ids.append(other.claim_id)
                    assigned.add(other.claim_id)
            group_id = f"sg_{gid}"
            gid += 1
            groups.append(
                {
                    "group_id": group_id,
                    "section": section,
                    "subsection": subsection,
                    "claim_ids": member_ids,
                }
            )
            for c in bucket:
                if c.claim_id in member_ids:
                    c.similarity_group = group_id
    return groups


def _coverage_gaps(bucket: list[ClaimUnit]) -> list[str]:
    gaps: list[str] = []
    if not any(claim.outcome_impact for claim in bucket):
        gaps.append("missing_outcome")
    if not any(SCALE_RE.search(claim.claim_text) for claim in bucket):
        gaps.append("missing_scale")
    ownership_terms = ("owned", "led", "took", "architected", "designed", "built", "implemented")
    if not any(any(term in _norm(claim.claim_text) for term in ownership_terms) for claim in bucket):
        gaps.append("missing_ownership_scope")
    if not any(claim.method_tool for claim in bucket):
        gaps.append("missing_tool_specificity")
    return gaps


def build_evidence(
    work_exp: dict[str, Any],
    store: dict[str, Any],
    keywords: dict[str, list[str]],
    selections: dict[str, Any],
    template_map: dict[str, Any] | None = None,
) -> dict[str, Any]:
    excluded = set(selections.get("excluded", []))
    partial = set(selections.get("partial", []))

    claims = _build_work_claims(work_exp, keywords) + _build_project_claims(store, keywords, excluded, partial)
    similarity_groups = _assign_similarity_groups(claims)
    group_size = {g["group_id"]: len(g["claim_ids"]) for g in similarity_groups}

    evidence_packs: list[dict[str, Any]] = []
    by_subsection: dict[tuple[str, str], list[ClaimUnit]] = {}
    for claim in claims:
        by_subsection.setdefault((claim.section, claim.subsection), []).append(claim)

    template_slot_lookup: dict[tuple[str, str], int] = {}
    if template_map:
        for section in ("work_experience", "technical_projects"):
            for sub_name, meta in template_map.get(section, {}).items():
                template_slot_lookup[(section, _norm(sub_name))] = len(meta.get("bullet_xpaths", []))

    claim_lookup = {claim.claim_id: asdict(claim) for claim in claims}

    for (section, subsection), bucket in sorted(by_subsection.items()):
        scored = sorted(
            bucket,
            key=lambda c: (
                len(c.keyword_links),
                bool(c.outcome_impact),
                len(c.method_tool),
                _confidence_weight(c.confidence),
            ),
            reverse=True,
        )
        seen_groups: set[str] = set()
        eligible: list[str] = []
        blocked: list[dict[str, str]] = []
        for claim in scored:
            if claim.explicit_not_risk:
                blocked.append({"claim_id": claim.claim_id, "reason": "explicit_not_risk"})
                continue
            if claim.similarity_group in seen_groups:
                blocked.append({"claim_id": claim.claim_id, "reason": "duplicate_similarity_group"})
                continue
            seen_groups.add(claim.similarity_group)
            eligible.append(claim.claim_id)

        subsection_id = normalize_subsection_id(section, subsection)
        slot_count = template_slot_lookup.get((section, _norm(subsection)), 0)
        keyword_targets = []
        for claim_id in eligible:
            for kw in claim_lookup[claim_id].get("keyword_links", []):
                if kw not in keyword_targets:
                    keyword_targets.append(kw)

        pack = {
            "section": section,
            "subsection": subsection,
            "subsection_id": subsection_id,
            "slot_count": slot_count,
            "eligible_claim_ids": eligible,
            "allowed_fact_ids": eligible,
            "blocked_claim_ids": blocked,
            "disallowed_claims": blocked,
            "coverage_gaps": _coverage_gaps(bucket),
            "partial_contribution": any(claim.partial_contribution for claim in bucket),
            "partial_contribution_flag": any(claim.partial_contribution for claim in bucket),
            "project_name": next((c.project_name for c in bucket if c.project_name), ""),
            "project_title": next((c.project_title for c in bucket if c.project_title), ""),
            "tech_tags": next(
                (
                    project.get("tech_tags", [])
                    for project in store.get("projects", [])
                    if project.get("title") == subsection or project.get("name") == next((c.project_name for c in bucket if c.project_name), "")
                ),
                [],
            ),
            "similarity_groups_in_scope": sorted(
                {claim.similarity_group for claim in bucket if claim.similarity_group}
            ),
            "duplicate_pressure": sum(1 for claim in bucket if group_size.get(claim.similarity_group, 0) > 1),
            "keyword_targets": keyword_targets,
            "priority_facts": eligible[: min(5, len(eligible))],
        }
        evidence_packs.append(pack)

    return {
        "schema_version": 1,
        "keywords": keywords,
        "claim_units": [asdict(claim) for claim in claims],
        "similarity_groups": similarity_groups,
        "evidence_packs": evidence_packs,
    }


def _parse_keywords(raw: dict[str, Any]) -> dict[str, list[str]]:
    if not raw:
        return {"required": [], "nice_to_have": []}
    if "keywords" in raw and isinstance(raw["keywords"], dict):
        source = raw["keywords"]
    else:
        source = raw
    return {
        "required": list(source.get("required", [])),
        "nice_to_have": list(source.get("nice_to_have", [])),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build claim-graph evidence packs for CV planning")
    parser.add_argument("--work-exp", required=True, help="Path to .cv-work-experience.json")
    parser.add_argument("--store", required=True, help="Path to .cv-harvest-store.json")
    parser.add_argument("--keywords", required=True, help="Path to extracted keyword JSON")
    parser.add_argument("--project-selections", required=True, help="Path to .cv-apply-project-selections.json")
    parser.add_argument("--template-map", help="Optional template_map.json for slot_count alignment")
    parser.add_argument("--out", required=True, help="Output path for evidence pack JSON")
    args = parser.parse_args()

    work_exp = _load_json(Path(args.work_exp), default={})
    store = _load_json(Path(args.store), default={})
    keywords = _parse_keywords(_load_json(Path(args.keywords), default={}))
    selections = _load_json(Path(args.project_selections), default={})
    template_map = _load_json(Path(args.template_map), default={}) if args.template_map else None

    payload = build_evidence(work_exp, store, keywords, selections, template_map=template_map)
    out_path = Path(args.out)
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(str(out_path))


if __name__ == "__main__":
    main()
