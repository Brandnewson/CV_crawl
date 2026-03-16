import json
from collections import Counter

data = {
  "job_id": 4103,
  "user_id": 1,
  "session_timestamp": "2026-03-14T00:00:00Z",
  "hidden_projects": [],
  "header_swaps": [
    {"section": "technical_projects", "subsection": "Formula Student Lap Time Simulator", "header_xpath_index": 0, "text": "Agentic CV & Cover Letter Pipeline | Python, React, TypeScript, LLMs, REST API"},
    {"section": "technical_projects", "subsection": "Radiator Thermal Management Simulator", "header_xpath_index": 1, "text": "Aerodynamic Concept RAG Analyser | Python, RAG, FastAPI, React, LLMs"},
    {"section": "technical_projects", "subsection": "2D CFD Formula Student Radiator Optimisation", "header_xpath_index": 2, "text": "F1 Race Strategy MARL Simulator | Python, PyTorch, DQN, Claude API, LLMs"},
    {"section": "technical_projects", "subsection": "Formula Student ICE Data Acquisition", "header_xpath_index": 3, "text": "Wing Aerodynamic Analyser API | Python, FastAPI, REST API, Claude API, LLMs"},
    {"section": "technical_projects", "subsection": "Formula Student EV Battery Management", "header_xpath_index": 4, "text": "Job Search Intelligence Tooling | Python, PostgreSQL, Claude Code, NLP, CLI"}
  ],
  "approved_bullets": [
    {"slot_index": 0, "section": "work_experience", "subsection": "Jaguar TCS Racing", "text": "Designed REST and WebSocket APIs for streaming live race telemetry to React dashboards used trackside", "source": "rephrasing", "rephrase_generation": 0},
    {"slot_index": 1, "section": "work_experience", "subsection": "Jaguar TCS Racing", "text": "Engineered a Node.js ingestion service parsing WinTax telemetry CSV into JSON schema for downstream apps", "source": "rephrasing", "rephrase_generation": 0},
    {"slot_index": 2, "section": "work_experience", "subsection": "Jaguar TCS Racing", "text": "Developed full-stack React and TypeScript dashboards surfacing time-critical race data to track engineers", "source": "rephrasing", "rephrase_generation": 0},
    {"slot_index": 3, "section": "work_experience", "subsection": "Jaguar TCS Racing", "text": "Architected containerised microservices deployed via Docker and AWS ECS Fargate for race-weekend reliability", "source": "rephrasing", "rephrase_generation": 0},
    {"slot_index": 4, "section": "work_experience", "subsection": "Jaguar TCS Racing", "text": "Delivered forward deployed tooling in trackside environments supporting engineers during live race operations", "source": "rephrasing", "rephrase_generation": 0},
    {"slot_index": 5, "section": "work_experience", "subsection": "Jaguar TCS Racing", "text": "Onboarded race engineers onto new internal tools through direct customer onboarding sessions trackside", "source": "rephrasing", "rephrase_generation": 0},
    {"slot_index": 6, "section": "work_experience", "subsection": "Jaguar TCS Racing", "text": "Integrated FIA timing feeds and McLaren ATLAS APIs as third-party integrations into team data systems", "source": "rephrasing", "rephrase_generation": 0},
    {"slot_index": 7, "section": "work_experience", "subsection": "Jaguar TCS Racing", "text": "Managed concurrent projects against race-weekend hard deadlines across timing and telemetry pipelines", "source": "rephrasing", "rephrase_generation": 0},
    {"slot_index": 8, "section": "work_experience", "subsection": "Jaguar TCS Racing", "text": "Collaborated on a transcription pipeline using speech-to-text libraries for driver radio voice tuning", "source": "rephrasing", "rephrase_generation": 0},
    {"slot_index": 9, "section": "work_experience", "subsection": "Jaguar TCS Racing", "text": "Created a Python data-processing pipeline converting NoSQL race data into processed telemetry channels", "source": "rephrasing", "rephrase_generation": 0},
    {"slot_index": 10, "section": "work_experience", "subsection": "Jaguar TCS Racing", "text": "Deployed CNN and OpenCV-based image recognition tooling applied to real-time race analysis workflows", "source": "rephrasing", "rephrase_generation": 0},
    {"slot_index": 11, "section": "work_experience", "subsection": "Jaguar TCS Racing", "text": "Authored Atlas_BT Python library enabling programmatic read-write of ATLAS binary telemetry formats", "source": "rephrasing", "rephrase_generation": 0},
    {"slot_index": 12, "section": "work_experience", "subsection": "Jaguar TCS Racing", "text": "Took full ownership of the Timing Feed Service designing and shipping a production system race engineers rely on", "source": "rephrasing", "rephrase_generation": 0},
    {"slot_index": 0, "section": "work_experience", "subsection": "Republic of Singapore Navy", "text": "Analysed live sensor data from core ship systems via telemetry displays under high-pressure scenarios", "source": "rephrasing", "rephrase_generation": 0},
    {"slot_index": 1, "section": "work_experience", "subsection": "Republic of Singapore Navy", "text": "Led remote wartime firefighting simulation aboard ship assigning fixes from the engine operations room", "source": "rephrasing", "rephrase_generation": 0},
    {"slot_index": 2, "section": "work_experience", "subsection": "Republic of Singapore Navy", "text": "Mentored teams of up to 10 junior personnel on marine technical systems and mission-critical procedures", "source": "rephrasing", "rephrase_generation": 0},
    {"slot_index": 3, "section": "work_experience", "subsection": "Republic of Singapore Navy", "text": "Contributed to 50 pre- and post-mission debriefs identifying improvements to team efficiency and safety", "source": "rephrasing", "rephrase_generation": 0},
    {"slot_index": 4, "section": "work_experience", "subsection": "Republic of Singapore Navy", "text": "Trained reservists on 4-stroke and 2-stroke engine operation bridging gaps in marine systems knowledge", "source": "rephrasing", "rephrase_generation": 0},
    {"slot_index": 0, "section": "work_experience", "subsection": "Travelindr", "text": "Founded Travelindr in a cross-functional Agile team and progressed the product from concept to MVP stage", "source": "rephrasing", "rephrase_generation": 0},
    {"slot_index": 1, "section": "work_experience", "subsection": "Travelindr", "text": "Conducted user interviews and A/B testing with potential customers to inform iterative product direction", "source": "rephrasing", "rephrase_generation": 0},
    {"slot_index": 2, "section": "work_experience", "subsection": "Travelindr", "text": "Communicated product decisions and A/B test results to non-technical stakeholders securing incubation", "source": "rephrasing", "rephrase_generation": 0},
    {"slot_index": 0, "section": "technical_projects", "subsection": "Formula Student Lap Time Simulator", "text": "Architected a multi-agent LLM pipeline for automated job discovery and intelligent CV tailoring in Python", "source": "rephrasing", "rephrase_generation": 0},
    {"slot_index": 1, "section": "technical_projects", "subsection": "Formula Student Lap Time Simulator", "text": "Built a React and TypeScript frontend backed by a Python API for end-to-end user-driven pipeline config", "source": "rephrasing", "rephrase_generation": 0},
    {"slot_index": 2, "section": "technical_projects", "subsection": "Formula Student Lap Time Simulator", "text": "Implemented JD keyword coverage analysis producing quantified match scoring to optimise role relevance", "source": "rephrasing", "rephrase_generation": 0},
    {"slot_index": 0, "section": "technical_projects", "subsection": "Radiator Thermal Management Simulator", "text": "Constructed a RAG pipeline ingesting arXiv papers into a vector database for LLM-synthesised evaluation", "source": "rephrasing", "rephrase_generation": 0},
    {"slot_index": 1, "section": "technical_projects", "subsection": "Radiator Thermal Management Simulator", "text": "Built a REST API backend with MCP integration exposing aerodynamic concept queries to a React frontend", "source": "rephrasing", "rephrase_generation": 0},
    {"slot_index": 0, "section": "technical_projects", "subsection": "2D CFD Formula Student Radiator Optimisation", "text": "Developed a multi-agent DQN race strategy simulator consuming real-time fastF1 telemetry for AI solutions", "source": "rephrasing", "rephrase_generation": 0},
    {"slot_index": 1, "section": "technical_projects", "subsection": "2D CFD Formula Student Radiator Optimisation", "text": "Integrated a Claude API autoresearch loop for automated hyperparameter optimisation of DQN agent configs", "source": "rephrasing", "rephrase_generation": 0},
    {"slot_index": 0, "section": "technical_projects", "subsection": "Formula Student ICE Data Acquisition", "text": "Designed a FastAPI REST API for aerodynamic analysis integrating Claude Sonnet as the LLM reasoning layer", "source": "rephrasing", "rephrase_generation": 0},
    {"slot_index": 1, "section": "technical_projects", "subsection": "Formula Student ICE Data Acquisition", "text": "Applied LLM prompting via the Claude API to interpret aerodynamic parameters and return structured outputs", "source": "rephrasing", "rephrase_generation": 0},
    {"slot_index": 0, "section": "technical_projects", "subsection": "Formula Student EV Battery Management", "text": "Built a PostgreSQL-backed job query tool performing ranked JOIN queries with fit-score thresholding", "source": "rephrasing", "rephrase_generation": 0},
    {"slot_index": 1, "section": "technical_projects", "subsection": "Formula Student EV Battery Management", "text": "Refined agentic automation workflows using Claude Code for multi-step orchestration and pipeline patterns", "source": "rephrasing", "rephrase_generation": 0}
  ]
}

open("C:/Code/CV_crawl/.cv-apply-selections-tmp.json", "w", encoding="utf-8").write(json.dumps(data, indent=2))
print("Saved to .cv-apply-selections-tmp.json")

print("\n=== CHAR COUNTS ===")
hard_fail = []
soft_warn = []
for b in data["approved_bullets"]:
    l = len(b["text"])
    flag = "HARD_FAIL" if l > 110 else ("SHORT" if l < 95 else "OK")
    if l > 110:
        hard_fail.append(b)
    if l < 95:
        soft_warn.append({"bullet": b, "len": l})
    print(f"  [{l:3d}] {flag:9} | {b['subsection'][:22]:22} s{b['slot_index']} | {b['text'][:55]}")

print(f"\nHard failures (>110): {len(hard_fail)}")
for f in hard_fail:
    print(f"  [{len(f['text'])}] {f['subsection']} s{f['slot_index']}: {f['text']}")

print(f"\nShort bullets (<95): {len(soft_warn)}")
for w in soft_warn:
    print(f"  [{w['len']}] {w['bullet']['subsection']} s{w['bullet']['slot_index']}: {w['bullet']['text']}")

verbs = [b["text"].split()[0].lower() for b in data["approved_bullets"]]
vc = Counter(verbs)
print("\n=== VERB COUNTS (>=2) ===")
for v, c in sorted(vc.items(), key=lambda x: -x[1]):
    if c >= 2:
        print(f"  {v}: {c}")
