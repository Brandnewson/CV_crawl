"""Patch keyword_targets in slot plan to resolve validator conflicts."""
import json
from pathlib import Path

sp_path = Path(r"C:\Code\CV_crawl\.cv-apply-slot-plan-tmp.json")
sp = json.loads(sp_path.read_text(encoding="utf-8"))

patches = {
    # (section, subsection, slot_index): new keyword_target
    ("work_experience", "Jaguar TCS Racing", 2): "",           # NoSQL pipeline — kubernetes explicit_not
    ("work_experience", "Jaguar TCS Racing", 3): "CI/CD",      # CI/CD is in bullet, enterprise deployment phrase isn't
    ("work_experience", "Republic of Singapore Navy", 2): "",   # helicopters ≠ CI/CD
    ("technical_projects", "F1 Race Strategy MARL Simulator", 0): "",  # user has no fine-tuning
    ("technical_projects", "Agentic CV & Cover Letter Pipeline", 0): "LLM workflows",  # bullet hits LLM workflows
}

for card in sp.get("bullet_intent_cards", []):
    key = (card["section"], card["subsection"], card["slot_index"])
    if key in patches:
        card["keyword_target"] = patches[key]
        card["keyword_target_norm"] = patches[key].lower()
        if patches[key] == "":
            card["coverage_mode"] = "implicit"
        print(f"Patched {key} -> '{patches[key]}'")

for card in sp.get("writer_brief_cards", []):
    key = (card["section"], card["subsection"], card["slot_index"])
    if key in patches:
        card["keyword_target"] = patches[key]
        card["keyword_target_norm"] = patches[key].lower()
        if patches[key] == "":
            card["coverage_mode"] = "implicit"

sp_path.write_text(json.dumps(sp, indent=2, ensure_ascii=False), encoding="utf-8")
print("Slot plan patched and saved.")
