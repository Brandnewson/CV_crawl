import json, pathlib

sp_path = pathlib.Path(r"C:\Code\CV_crawl\.cv-apply-slot-plan-tmp.json")
sp = json.loads(sp_path.read_text(encoding="utf-8"))

# Fix keyword_targets: simplify slash-compound targets and fix wrong "RAG" on Jaguar slot 3
fixes = {
    ("work_experience", "Jaguar TCS Racing", 3): "systems design",
    ("technical_projects", "F1 Race Strategy MARL Simulator", 0): "machine learning",
    ("technical_projects", "F1 Race Strategy MARL Simulator", 1): "",
    ("technical_projects", "Aerodynamic Concept RAG Analyser", 0): "RAG",
    ("technical_projects", "Aerodynamic Concept RAG Analyser", 1): "LLMs",
}

for card in sp["bullet_intent_cards"]:
    key = (card.get("section",""), card.get("subsection",""), card.get("slot_index",0))
    if key in fixes:
        old = card.get("keyword_target","")
        card["keyword_target"] = fixes[key]
        print(f"Patched [{key}]: '{old}' -> '{fixes[key]}'")

sp_path.write_text(json.dumps(sp, indent=2, ensure_ascii=False), encoding="utf-8")
print("Slot plan patched.")
