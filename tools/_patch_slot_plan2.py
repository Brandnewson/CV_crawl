"""Patch slot plan: make Jaguar slots 0 and 2 explicit with 'python'."""
import json
from pathlib import Path

sp_path = Path(r"C:\Code\CV_crawl\.cv-apply-slot-plan-tmp.json")
sp = json.loads(sp_path.read_text(encoding="utf-8"))

make_explicit = {
    ("work_experience", "Jaguar TCS Racing", 0): "python",
    ("work_experience", "Jaguar TCS Racing", 2): "python",
}

for card in sp.get("bullet_intent_cards", []) + sp.get("writer_brief_cards", []):
    key = (card["section"], card["subsection"], card["slot_index"])
    if key in make_explicit:
        card["keyword_target"] = make_explicit[key]
        card["keyword_target_norm"] = make_explicit[key]
        card["coverage_mode"] = "explicit"
        print(f"Made explicit {key} -> '{make_explicit[key]}'")

sp_path.write_text(json.dumps(sp, indent=2, ensure_ascii=False), encoding="utf-8")
print("Done.")
