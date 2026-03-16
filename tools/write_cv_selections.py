"""Write the current CV selections temp file. Run directly with uv or python."""
import json
from pathlib import Path

bullets = [
    # Jaguar TCS Racing — 13 slots (HappyRobot FDE tailored)
    (0,"work_experience","Jaguar TCS Racing","Built and deployed forward-deployed race-weekend tools actively used in live Formula E trackside operations."),
    (1,"work_experience","Jaguar TCS Racing","Developed full-stack React/TypeScript dashboards for real-time telemetry visualisation across race weekends."),
    (2,"work_experience","Jaguar TCS Racing","Designed REST and WebSocket APIs integrating third-party live timing feeds from FIA and Al Kamel systems."),
    (3,"work_experience","Jaguar TCS Racing","Built a Node.js ingestion service parsing WinTax race telemetry CSV into structured JSON over WebSocket."),
    (4,"work_experience","Jaguar TCS Racing","Architected containerised microservices using Docker and AWS ECS to deliver cloud-native scalable solutions."),
    (5,"work_experience","Jaguar TCS Racing","Developed Atlas_BT, a Python library enabling read and write access to ATLAS binary telemetry data formats."),
    (6,"work_experience","Jaguar TCS Racing","Onboarded race engineers onto new internal tools through hands-on telemetry dashboard training sessions."),
    (7,"work_experience","Jaguar TCS Racing","Implemented CI/CD pipelines via GitHub Actions and deployed containerised services to Azure infrastructure."),
    (8,"work_experience","Jaguar TCS Racing","Managed multiple concurrent engineering projects against hard race-weekend deadlines across the season."),
    (9,"work_experience","Jaguar TCS Racing","Contributed to a speech-to-text pipeline transcribing driver radio comms and feeding LLM summarisation."),
    (10,"work_experience","Jaguar TCS Racing","Took full ownership of the Timing Feed Service end-to-end, acting with a founder mindset to drive delivery."),
    (11,"work_experience","Jaguar TCS Racing","Analysed ATLAS race telemetry to optimise energy management strategies and deliver lap-time improvements."),
    (12,"work_experience","Jaguar TCS Racing","Communicated telemetry pipeline architecture clearly to race engineers less familiar with software systems."),
    # Republic of Singapore Navy — 5 slots
    (0,"work_experience","Republic of Singapore Navy","Analysed live sensor telemetry from core ship systems under high-pressure operational conditions at sea."),
    (1,"work_experience","Republic of Singapore Navy","Led remote wartime damage-control and firefighting simulations aboard the Singapore Navy's flagship vessel."),
    (2,"work_experience","Republic of Singapore Navy","Mentored teams of up to 10 personnel on technical marine systems operation, including propulsion engines."),
    (3,"work_experience","Republic of Singapore Navy","Contributed to over 50 pre- and post-mission debriefs informing corrective actions for mission-critical ops."),
    (4,"work_experience","Republic of Singapore Navy","Trained returning reservists on 4-stroke and 2-stroke marine engine operation after extended service gaps."),
    # Travelindr — 3 slots
    (0,"work_experience","Travelindr","Founded and shipped a travel-itinerary MVP, running iterative A/B testing to validate with early customers."),
    (1,"work_experience","Travelindr","Conducted customer-facing user interviews and focus groups with real users to shape product direction."),
    (2,"work_experience","Travelindr","Pitched to early-stage investors and secured incubation within a multinational company at pre-seed stage."),
    # Agentic CV & Cover Letter Pipeline — 3 slots (uses ORIGINAL template slot name)
    (0,"technical_projects","Formula Student Lap Time Simulator","Architected a multi-agent LLM pipeline orchestrating specialist sub-agents for JD analysis and CV tailoring."),
    (1,"technical_projects","Formula Student Lap Time Simulator","Built a full-stack React/TypeScript frontend backed by a Python REST API for end-to-end CV configuration."),
    (2,"technical_projects","Formula Student Lap Time Simulator","Designed LLM prompting chains for JD keyword extraction, enforcing strict character limits and tone rules."),
    # Aerodynamic Concept RAG Analyser — 2 slots
    (0,"technical_projects","Radiator Thermal Management Simulator","Built a RAG pipeline ingesting arXiv aerodynamics papers into a vector store for LLM-synthesised analysis."),
    (1,"technical_projects","Radiator Thermal Management Simulator","Implemented a REST API with MCP server integration exposing structured tool endpoints to a React frontend."),
    # F1 Race Strategy MARL Simulator — 2 slots
    (0,"technical_projects","2D CFD Formula Student Radiator Optimisation Simulator","Developed a multi-agent DQN race strategy simulator producing trained policy model snapshots each episode."),
    (1,"technical_projects","2D CFD Formula Student Radiator Optimisation Simulator","Integrated a Claude API auto-research loop enabling iterative automated hyperparameter optimisation runs."),
    # Azure Serverless Distributed Pipeline — 2 slots
    (0,"technical_projects","Formula Student ICE Data Acquisition System","Designed a distributed serverless pipeline using Azure Functions with event-driven HTTP trigger routing."),
    (1,"technical_projects","Formula Student ICE Data Acquisition System","Conducted load and stress testing to validate throughput under simulated high-frequency data ingestion."),
    # Wing Aerodynamic Analyser API — 2 slots
    (0,"technical_projects","Formula Student EV Battery Management System","Designed a FastAPI REST API integrating Claude as the LLM reasoning layer for aerodynamic domain analysis."),
    (1,"technical_projects","Formula Student EV Battery Management System","Applied LLM prompting via the Claude API to generate structured aerodynamic performance analysis outputs."),
]

selections = {
    "job_id": 4103,
    "user_id": 1,
    "session_timestamp": "2026-03-14T01:10:00Z",
    "hidden_projects": [],
    "header_swaps": [
        {"section": "technical_projects", "subsection": "Formula Student Lap Time Simulator", "header_xpath_index": 0, "text": "Agentic CV & Cover Letter Pipeline | Python, React, TypeScript, LLMs, REST API"},
        {"section": "technical_projects", "subsection": "Radiator Thermal Management Simulator", "header_xpath_index": 0, "text": "Aerodynamic Concept RAG Analyser | Python, RAG, FastAPI, React, MCP"},
        {"section": "technical_projects", "subsection": "2D CFD Formula Student Radiator Optimisation Simulator", "header_xpath_index": 0, "text": "F1 Race Strategy MARL Simulator | Python, PyTorch, DQN, Claude API, fastF1"},
        {"section": "technical_projects", "subsection": "Formula Student ICE Data Acquisition System", "header_xpath_index": 0, "text": "Azure Serverless Distributed Pipeline | Python, Azure Functions, Cloud"},
        {"section": "technical_projects", "subsection": "Formula Student EV Battery Management System", "header_xpath_index": 0, "text": "Wing Aerodynamic Analyser API | Python, FastAPI, Claude API, LLMs"},
    ],
    "approved_bullets": [
        {"slot_index": si, "section": sec, "subsection": sub, "text": txt, "source": "rephrasing", "rephrase_generation": 0}
        for si, sec, sub, txt in bullets
    ],
}

out = Path(r"C:\Code\CV_crawl\.cv-apply-selections-tmp.json")
out.write_text(json.dumps(selections, indent=2, ensure_ascii=False), encoding="utf-8")

over = [(b["subsection"], b["slot_index"], len(b["text"])) for b in selections["approved_bullets"] if len(b["text"]) > 120]
print(f"Written {len(bullets)} bullets. Over 120 chars: {len(over)}")
for s, i, n in over:
    print(f"  [{s}] slot {i}: {n} chars")
