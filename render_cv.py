import json, re, sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, r"C:\Code\CV_CoverLetter_Generator_Agentic_Pipeline\job-pipeline")
from agent.cv_renderer import render_cv
from agent.validators import UserSelections

meta  = json.loads(open(r"C:\Code\CV_crawl\.cv-apply-meta-tmp.json",       encoding="utf-8").read())
sdata = json.loads(open(r"C:\Code\CV_crawl\.cv-apply-selections-tmp.json", encoding="utf-8").read())
selections = UserSelections(**sdata)

safe_company = re.sub(r'[^\w\-]', '_', meta["company"])
safe_role    = re.sub(r'[^\w\-]', '_', meta["job_title"])[:30]
out_path = Path(rf"C:\Users\brans\OneDrive - University of Leeds\GraduateJobHunting\claude-cv-outputs\{safe_company}_{safe_role}_{datetime.now().strftime('%Y%m%d')}.docx")

render_cv(
    template_path=Path(r"C:\Code\CV_CoverLetter_Generator_Agentic_Pipeline\job-pipeline\profile\cv_template.docx"),
    template_map_path=Path(r"C:\Code\CV_CoverLetter_Generator_Agentic_Pipeline\job-pipeline\profile\template_map.json"),
    selections=selections,
    job={"job_id": meta["job_id"], "title": meta["job_title"], "company": meta["company"]},
    output_path=out_path,
)
print(str(out_path))
