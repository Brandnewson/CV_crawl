import json, pathlib

# Fixed bullets addressing all validation failures:
# 1. Jaguar slot 1: trimmed to 110 chars, more distinct from slot 0
# 2. Jaguar slot 2: rephrased to be distinct, now "Wired..."
# 3. Jaguar slot 3: "systems design" now appears verbatim
# 4. F1 MARL slot 0: "machine learning" appears verbatim
# 5. F1 MARL slot 1: "data pipeline" appears verbatim
# 6. Aero RAG slot 0: "RAG" appears verbatim
# 7. Aero RAG slot 1: "LLMs" appears verbatim

bullets = [
  {"slot_index":0,"section":"work_experience","subsection":"Jaguar TCS Racing","text":"Built a Python data pipeline converting NoSQL race data into processed telemetry channels for engineers","intent_id":"intent_work_jaguar_tcs_racing_0","provenance":{"primary_claim_id":"work_jaguar_tcs_racing_16","secondary_claim_ids":[],"source_ref":{"source":".cv-work-experience.json","org":"Jaguar TCS Racing","fact_index":16}},"source":"rephrasing","rephrase_generation":0},
  {"slot_index":1,"section":"work_experience","subsection":"Jaguar TCS Racing","text":"Developed Atlas_BT, a Python library with programmatic read-write access to ATLAS binary telemetry","intent_id":"intent_work_jaguar_tcs_racing_1","provenance":{"primary_claim_id":"work_jaguar_tcs_racing_2","secondary_claim_ids":[],"source_ref":{"source":".cv-work-experience.json","org":"Jaguar TCS Racing","fact_index":2}},"source":"rephrasing","rephrase_generation":1},
  {"slot_index":2,"section":"work_experience","subsection":"Jaguar TCS Racing","text":"Streamed live FIA timing feeds via custom Python libraries into the processing backend, on-site and cloud","intent_id":"intent_work_jaguar_tcs_racing_2","provenance":{"primary_claim_id":"work_jaguar_tcs_racing_0","secondary_claim_ids":[],"source_ref":{"source":".cv-work-experience.json","org":"Jaguar TCS Racing","fact_index":0}},"source":"rephrasing","rephrase_generation":1},
  {"slot_index":3,"section":"work_experience","subsection":"Jaguar TCS Racing","text":"Drove systems design analysis by evaluating technology tradeoffs against business and scalability constraints","intent_id":"intent_work_jaguar_tcs_racing_3","provenance":{"primary_claim_id":"work_jaguar_tcs_racing_3","secondary_claim_ids":[],"source_ref":{"source":".cv-work-experience.json","org":"Jaguar TCS Racing","fact_index":3}},"source":"rephrasing","rephrase_generation":1},
  {"slot_index":4,"section":"work_experience","subsection":"Jaguar TCS Racing","text":"Authored Python strategy scripts used in live race production contexts to inform real-time tactical decisions","intent_id":"intent_work_jaguar_tcs_racing_4","provenance":{"primary_claim_id":"work_jaguar_tcs_racing_5","secondary_claim_ids":[],"source_ref":{"source":".cv-work-experience.json","org":"Jaguar TCS Racing","fact_index":5}},"source":"rephrasing","rephrase_generation":0},
  {"slot_index":5,"section":"work_experience","subsection":"Jaguar TCS Racing","text":"Deployed race data services to Azure cloud infrastructure, expanding remote analysis capabilities","intent_id":"intent_work_jaguar_tcs_racing_5","provenance":{"primary_claim_id":"work_jaguar_tcs_racing_7","secondary_claim_ids":[],"source_ref":{"source":".cv-work-experience.json","org":"Jaguar TCS Racing","fact_index":7}},"source":"rephrasing","rephrase_generation":0},
  {"slot_index":6,"section":"work_experience","subsection":"Jaguar TCS Racing","text":"Managed Azure DevOps work items to align software delivery with stakeholder requirements each sprint","intent_id":"intent_work_jaguar_tcs_racing_6","provenance":{"primary_claim_id":"work_jaguar_tcs_racing_18","secondary_claim_ids":[],"source_ref":{"source":".cv-work-experience.json","org":"Jaguar TCS Racing","fact_index":18}},"source":"rephrasing","rephrase_generation":0},
  {"slot_index":0,"section":"work_experience","subsection":"Republic of Singapore Navy","text":"Trained reservists in 4-stroke and 2-stroke engine operation through structured technical instruction sessions","intent_id":"intent_work_republic_of_singapore_navy_0","provenance":{"primary_claim_id":"work_republic_of_singapore_navy_1","secondary_claim_ids":[],"source_ref":{"source":".cv-work-experience.json","org":"Republic of Singapore Navy","fact_index":1}},"source":"rephrasing","rephrase_generation":0},
  {"slot_index":1,"section":"work_experience","subsection":"Republic of Singapore Navy","text":"Led a team of up to 10 personnel, coordinating operations and maintaining readiness across naval service duties","intent_id":"intent_work_republic_of_singapore_navy_1","provenance":{"primary_claim_id":"work_republic_of_singapore_navy_4","secondary_claim_ids":[],"source_ref":{"source":".cv-work-experience.json","org":"Republic of Singapore Navy","fact_index":4}},"source":"rephrasing","rephrase_generation":0},
  {"slot_index":2,"section":"work_experience","subsection":"Republic of Singapore Navy","text":"Coordinated helicopter firefighting operations with crew under high-pressure emergency conditions","intent_id":"intent_work_republic_of_singapore_navy_2","provenance":{"primary_claim_id":"work_republic_of_singapore_navy_0","secondary_claim_ids":[],"source_ref":{"source":".cv-work-experience.json","org":"Republic of Singapore Navy","fact_index":0}},"source":"rephrasing","rephrase_generation":0},
  {"slot_index":0,"section":"work_experience","subsection":"Travelindr","text":"Co-founded Travelindr and drove product strategy from market insight through wireframed roadmap delivery","intent_id":"intent_work_travelindr_0","provenance":{"primary_claim_id":"work_travelindr_0","secondary_claim_ids":[],"source_ref":{"source":".cv-work-experience.json","org":"Travelindr","fact_index":0}},"source":"rephrasing","rephrase_generation":0},
  {"slot_index":1,"section":"work_experience","subsection":"Travelindr","text":"Conducted focus-group discussions to surface user insights and inform iterative UI mockup refinements","intent_id":"intent_work_travelindr_1","provenance":{"primary_claim_id":"work_travelindr_1","secondary_claim_ids":[],"source_ref":{"source":".cv-work-experience.json","org":"Travelindr","fact_index":1}},"source":"rephrasing","rephrase_generation":0},
  {"slot_index":0,"section":"technical_projects","subsection":"F1 Race Strategy MARL Simulator","text":"Engineered a multi-agent DQN simulator applying machine learning to F1 race strategy with LLM autoresearch","intent_id":"intent_proj_f1_race_strategy_marl_simulator_0","provenance":{"primary_claim_id":"proj_f1_strategysimulator_0","secondary_claim_ids":[],"source_ref":{"source":".cv-harvest-store.json","project_name":"F1_StrategySimulator","bullet_index":0}},"source":"rephrasing","rephrase_generation":1},
  {"slot_index":1,"section":"technical_projects","subsection":"F1 Race Strategy MARL Simulator","text":"Integrated a Claude API agentic loop for automated DQN hyperparameter optimisation without overrides","intent_id":"intent_proj_f1_race_strategy_marl_simulator_1","provenance":{"primary_claim_id":"proj_f1_strategysimulator_2","secondary_claim_ids":[],"source_ref":{"source":".cv-harvest-store.json","project_name":"F1_StrategySimulator","bullet_index":2}},"source":"rephrasing","rephrase_generation":1},
  {"slot_index":0,"section":"technical_projects","subsection":"Agentic CV & Cover Letter Pipeline","text":"Architected a Python multi-agent LLM pipeline orchestrating sub-agents for JD analysis and CV tailoring","intent_id":"intent_proj_agentic_cv_cover_letter_pipeline_0","provenance":{"primary_claim_id":"proj_cv_coverletter_generator_agentic_pipeline_0","secondary_claim_ids":[],"source_ref":{"source":".cv-harvest-store.json","project_name":"CV_CoverLetter_Generator_Agentic_Pipeline","bullet_index":0}},"source":"rephrasing","rephrase_generation":0},
  {"slot_index":0,"section":"technical_projects","subsection":"Aerodynamic Concept RAG Analyser","text":"Built a RAG pipeline indexing arXiv aerodynamics papers in a vector database for LLM-synthesised evaluation","intent_id":"intent_proj_aerodynamic_concept_rag_analyser_0","provenance":{"primary_claim_id":"proj_aerodynamic_rag_analyser_0","secondary_claim_ids":[],"source_ref":{"source":".cv-harvest-store.json","project_name":"aerodynamic_RAG__analyser","bullet_index":0}},"source":"rephrasing","rephrase_generation":0},
  {"slot_index":1,"section":"technical_projects","subsection":"Aerodynamic Concept RAG Analyser","text":"Integrated MCP tooling to extend retrieval with dynamic arXiv ingestion, exposing LLMs via a REST API","intent_id":"intent_proj_aerodynamic_concept_rag_analyser_1","provenance":{"primary_claim_id":"proj_aerodynamic_rag_analyser_2","secondary_claim_ids":[],"source_ref":{"source":".cv-harvest-store.json","project_name":"aerodynamic_RAG__analyser","bullet_index":2}},"source":"rephrasing","rephrase_generation":1},
]

data = {
  "job_id": 5841, "user_id": 1, "session_timestamp": "2026-03-18T11:30:00Z",
  "hidden_projects": [],
  "header_swaps": [
    {"section":"technical_projects","subsection":"F1 Race Strategy MARL Simulator","header_xpath_index":0,"text":"F1 Race Strategy MARL Simulator | Python, PyTorch, DQN, MARL, reinforcement learning, fastF1"},
    {"section":"technical_projects","subsection":"Agentic CV & Cover Letter Pipeline","header_xpath_index":0,"text":"Agentic CV & Cover Letter Pipeline | Python, React, TypeScript, LLMs, agentic systems, NLP"},
    {"section":"technical_projects","subsection":"Aerodynamic Concept RAG Analyser","header_xpath_index":0,"text":"Aerodynamic Concept RAG Analyser | Python, RAG, vector databases, LLMs, MCP, FastAPI"}
  ],
  "approved_bullets": bullets
}

# Verify char counts
print("Char count check:")
for b in bullets:
    n = len(b["text"])
    flag = "OK" if n <= 115 else "OVER"
    print(f"  [{flag}] {n:3d}  [{b['subsection'][:30]} s{b['slot_index']}] {b['text'][:60]}")

pathlib.Path(r"C:\Code\CV_crawl\.cv-apply-selections-tmp.json").write_text(
    json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
)
print(f"\nWritten {len(bullets)} bullets")
