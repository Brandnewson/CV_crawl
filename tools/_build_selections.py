"""Build and validate the HappyRobot selections JSON."""
import json
from pathlib import Path

bullets = [
    # Jaguar — 13 slots
    (0, "work_experience", "Jaguar TCS Racing",
     "Built AKS_Timing_Feed_Service unifying third-party FIA and Al Kamel timing data into a live race feed."),
    (1, "work_experience", "Jaguar TCS Racing",
     "Developed full-stack React and TypeScript telemetry dashboards delivered under tight race-weekend deadlines."),
    (2, "work_experience", "Jaguar TCS Racing",
     "Designed REST and WebSocket APIs streaming live WinTax telemetry for forward deployed engineering teams."),
    (3, "work_experience", "Jaguar TCS Racing",
     "Developed Atlas_BT, a Python library providing a programmable API for reading and writing ATLAS binary files."),
    (4, "work_experience", "Jaguar TCS Racing",
     "Led customer onboarding of race engineers onto new internal tools through hands-on telemetry training."),
    (5, "work_experience", "Jaguar TCS Racing",
     "Architected containerised microservices using Docker and AWS ECS as scalable solutions under race load."),
    (6, "work_experience", "Jaguar TCS Racing",
     "Built a Python pipeline converting NoSQL-stored race data into telemetry channels for AI/ML applications."),
    (7, "work_experience", "Jaguar TCS Racing",
     "Developed CNN and OpenCV image recognition tooling to apply AI/ML applications to live race visual analysis."),
    (8, "work_experience", "Jaguar TCS Racing",
     "Collaborated on ML/AI pipeline planning and a speech-to-text transcription pipeline for driver radio analysis."),
    (9, "work_experience", "Jaguar TCS Racing",
     "Managed multiple concurrent projects against tight race-weekend deadlines throughout the Formula E season."),
    (10, "work_experience", "Jaguar TCS Racing",
     "Resolved forward deployed issues in race-critical web tools trackside to maintain data-processing reliability."),
    (11, "work_experience", "Jaguar TCS Racing",
     "Took full ownership of the Timing Feed Service end-to-end with a founder mindset across the race season."),
    (12, "work_experience", "Jaguar TCS Racing",
     "Delivered per-session competitor analysis briefings to strategists covering energy, pit strategy and tyres."),
    # Navy — 5 slots
    (0, "work_experience", "Republic of Singapore Navy",
     "Served on Singapore Navy largest marine vessel as NCO Technical Specialist under high-pressure conditions."),
    (1, "work_experience", "Republic of Singapore Navy",
     "Trained reservists in 4-stroke and 2-stroke marine engine operation, translating technical concepts clearly."),
    (2, "work_experience", "Republic of Singapore Navy",
     "Guided reservists through wartime firefighting simulations and conducted pre- and post-mission debriefs."),
    (3, "work_experience", "Republic of Singapore Navy",
     "Participated in helicopter firefighting operations demanding rapid collaboration under high-stakes conditions."),
    (4, "work_experience", "Republic of Singapore Navy",
     "Developed structured debriefing routines that improved reservist retention of technical marine procedures."),
    # Travelindr — 3 slots
    (0, "work_experience", "Travelindr",
     "Co-founded Travelindr with a founder mindset, building a travel-itinerary MVP from concept to incubation."),
    (1, "work_experience", "Travelindr",
     "Ran iterative A/B tests and customer-facing user interviews to drive product decisions at MVP stage."),
    (2, "work_experience", "Travelindr",
     "Pitched to investors and secured incubation in a multinational company showcasing project management skills."),
    # Agentic CV Pipeline — 3 slots
    (0, "technical_projects", "Formula Student Lap Time Simulator",
     "Designed multi-stage LLM prompting chains for keyword extraction and CV tailoring producing targeted output."),
    (1, "technical_projects", "Formula Student Lap Time Simulator",
     "Orchestrated parallel sub-agents across code analysis and JD parsing to synthesise AI/ML applications for CV."),
    (2, "technical_projects", "Formula Student Lap Time Simulator",
     "Shipped a full-stack pipeline with CI/CD integrating Claude API to generate tailored cover letters at scale."),
    # RAG Analyser — 2 slots
    (0, "technical_projects", "Radiator Thermal Management Simulator",
     "Built a FastAPI REST API with authentication endpoints enabling third-party integrations with aero datasets."),
    (1, "technical_projects", "Radiator Thermal Management Simulator",
     "Implemented LLM prompting over a vector-indexed aerodynamic knowledge base to return scalable solutions."),
    # MARL Simulator — 2 slots
    (0, "technical_projects", "2D CFD Formula Student Radiator Optimisation Simulator",
     "Modelled multi-agent DQN race strategy interactions trained against energy management and tyre degradation."),
    (1, "technical_projects", "2D CFD Formula Student Radiator Optimisation Simulator",
     "Validated MARL simulator outputs against real ATLAS telemetry data to verify race strategy lap-time accuracy."),
    # Azure Pipeline — 2 slots
    (0, "technical_projects", "Formula Student ICE Data Acquisition System",
     "Architected a serverless Azure Functions pipeline converting NoSQL race data into structured telemetry."),
    (1, "technical_projects", "Formula Student ICE Data Acquisition System",
     "Containerised pipeline components using Docker and CI/CD to enable reliable deployments under tight deadlines."),
    # Wing API — 2 slots
    (0, "technical_projects", "Formula Student EV Battery Management System",
     "Developed a FastAPI REST API wrapping OpenCV image-analysis routines to extract aerodynamic surface metrics."),
    (1, "technical_projects", "Formula Student EV Battery Management System",
     "Shipped an MVP API with auto-generated docs enabling rapid customer onboarding for engineering users."),
]

selections = {
    "job_id": 4103,
    "user_id": 1,
    "session_timestamp": "2026-03-14T12:00:00Z",
    "hidden_projects": ["TyreDataVisualiser", "gra"],
    "header_swaps": [
        {"section": "technical_projects", "subsection": "Formula Student Lap Time Simulator",
         "header_xpath_index": 0, "text": "Agentic CV & Cover Letter Pipeline | Python, Claude API, LLM prompting, React, CI/CD"},
        {"section": "technical_projects", "subsection": "Radiator Thermal Management Simulator",
         "header_xpath_index": 0, "text": "Aerodynamic Concept RAG Analyser | Python, FastAPI, REST API, RAG, LLM prompting"},
        {"section": "technical_projects", "subsection": "2D CFD Formula Student Radiator Optimisation Simulator",
         "header_xpath_index": 0, "text": "F1 Race Strategy MARL Simulator | Python, MATLAB, Reinforcement Learning, Simulation"},
        {"section": "technical_projects", "subsection": "Formula Student ICE Data Acquisition System",
         "header_xpath_index": 0, "text": "Azure Serverless Distributed Pipeline | Python, Azure Functions, AKS, Docker, NoSQL"},
        {"section": "technical_projects", "subsection": "Formula Student EV Battery Management System",
         "header_xpath_index": 0, "text": "Wing Aerodynamic Analyser API | Python, FastAPI, REST API, OpenCV, NumPy"},
    ],
    "approved_bullets": [
        {"slot_index": si, "section": sec, "subsection": sub, "text": txt,
         "source": "rephrasing", "rephrase_generation": 0}
        for si, sec, sub, txt in bullets
    ],
}

out = Path(r"C:\Code\CV_crawl\.cv-apply-selections-tmp.json")
out.write_text(json.dumps(selections, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"Written {len(bullets)} bullets")
issues = []
for si, sec, sub, txt in bullets:
    n = len(txt)
    if n > 110:
        issues.append(f"  OVER {n}   s{si} [{sub[:28]}]: {txt[:60]}")
    elif n < 100:
        issues.append(f"  UNDER {n}  s{si} [{sub[:28]}]: {txt[:60]}")
if issues:
    print(f"LENGTH ISSUES ({len(issues)}):")
    for i in issues: print(i)
else:
    print("All bullets 100-110 chars OK")

banned = [(sub, si, txt) for si, sec, sub, txt in bullets if ":" in txt or ";" in txt]
if banned:
    print(f"BANNED PUNCTUATION:")
    for s, i, t in banned: print(f"  [{s[:28]}] s{i}: {t[:70]}")
else:
    print("No banned punctuation")

# Also print all lengths for review
print("\nAll bullet lengths:")
for si, sec, sub, txt in bullets:
    print(f"  {len(txt):3d}  s{si} {sub[:30]}")
