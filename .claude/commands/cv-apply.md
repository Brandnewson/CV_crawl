# /cv-apply — Tailored CV Generator

Takes a job from your PostgreSQL pipeline, runs gap-fill Q&A, writes a CV tailored
to that job, and produces a DOCX + PDF in `C:\Code\CV_crawl\output\`.

---

## Paths (hardcoded to your machine)

| Asset | Path |
|---|---|
| Experience store | `C:\Code\CV_crawl\.cv-harvest-store.json` |
| Work experience bank | `C:\Code\CV_crawl\.cv-work-experience.json` |
| Experience cache | `C:\Code\CV_crawl\.experience-cache.json` |
| CV template | `C:\Code\CV_CoverLetter_Generator_Agentic_Pipeline\job-pipeline\profile\cv_template.docx` |
| Template map | `C:\Code\CV_CoverLetter_Generator_Agentic_Pipeline\job-pipeline\profile\template_map.json` |
| Output dir | `C:\Users\brans\OneDrive - University of Leeds\GraduateJobHunting\claude-cv-outputs\` |
| Pipeline code | `C:\Code\CV_CoverLetter_Generator_Agentic_Pipeline\job-pipeline\` |
| uv project | `C:\Code\CV_CoverLetter_Generator_Agentic_Pipeline\job-pipeline\` |

## Python runtime

All Python must be run via uv so the pipeline's venv (psycopg2, lxml, pydantic, etc.) is active:

```
uv run --project "C:/Code/CV_CoverLetter_Generator_Agentic_Pipeline/job-pipeline" python <script> <args>
```

Never call bare `python` — always prefix with `uv run --project "C:/Code/CV_CoverLetter_Generator_Agentic_Pipeline/job-pipeline"`.

---

## ORCHESTRATOR — run this sequence

### Step 0 — Query ranked jobs from DB

Run (let it fail loudly if DB is unavailable — no fallbacks):

```
uv run --project "C:/Code/CV_CoverLetter_Generator_Agentic_Pipeline/job-pipeline" \
    python "C:/Code/CV_crawl/tools/query_jobs.py" --min-score 0.65 --status new --limit 20 --include-recent
```

If the command exits non-zero, surface the error message verbatim and stop. Do not offer
any fallback or alternative — the DB must be running and populated before using this command.

Parse the JSON output — it is a dict with keys `new_jobs` and `recent_jobs`.

Display the new jobs like this (use the `fit_summary` field for the summary line, truncated
to ~200 chars; use `job_url` for the link):

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
NEW JOBS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 1  0.90  CHAOS Industries — Forward Deployed Engineer - Software
          Defence AI startup — deploy sensing/ML products to field customers.
          https://jobs.chaosind.com/fde-software

 2  0.90  Procore Technologies — Forward Deployed Engineer (Datagrid)
          Construction SaaS — onsite customer data pipeline integration work.
          https://...
...
```

Then display the recent runs section (jobs from `recent_jobs`, using `cv_generated_at` for the date):

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RECENT RUNS  (select to regenerate or compare CVs)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
R1  Applied Intuition — Forward Deployed Engineer  [run 2026-03-12]
    Autonomous vehicles startup — technical deployment to car-maker customers.
    https://...

R2  HappyRobot — Forward Deployed Engineer  [run 2026-03-11]
    AI logistics startup — real-time freight negotiation platform deployment.
    https://...
```

If `recent_jobs` is empty, omit the RECENT RUNS section entirely.

Ask the user: **"Which job? Enter number (1–20) or R1–R5 to rerun:"**

When the user selects an R-number, load that job from `recent_jobs` and proceed exactly
as for a new job — all subsequent steps are identical. This allows regenerating or
refining a CV for a job already in the pipeline.

---

### Step 1 — Load and clean JD

1. Load the selected job's `description` field from the query results.
2. Write the raw JD description to `C:\Code\CV_crawl\.cv-apply-jd-tmp.txt`.
3. Attempt keyword extraction via subprocess:
```
uv run --project "C:/Code/CV_CoverLetter_Generator_Agentic_Pipeline/job-pipeline" python - <<'EOF'
import sys, json
sys.path.insert(0, r"C:\Code\CV_crawl")
sys.path.insert(0, r"C:\Code\CV_CoverLetter_Generator_Agentic_Pipeline\job-pipeline")
from tools.clean_jd import clean_jd
from agent.jd_parser import extract_keywords, classify_role_family

raw = open(r"C:\Code\CV_crawl\.cv-apply-jd-tmp.txt", encoding="utf-8").read()
jd_clean = clean_jd(raw)
keywords = extract_keywords(jd_clean)
role_family = classify_role_family(jd_clean)
print(json.dumps({"keywords": keywords, "role_family": role_family}))
EOF
```

**If the subprocess fails for any reason** (non-zero exit, import error, missing file, etc.), the orchestrator itself reads `.cv-apply-jd-tmp.txt` and extracts keywords directly:
- `required`: all specific technical terms, tools, languages, platforms, methodologies, and role-specific phrases marked "must have" or repeated ≥2× in the JD — aim for 15–25 items
- `nice_to_have`: all remaining non-trivial technical or domain terms — aim for 10–15 items
- Preserve exact JD phrasing (e.g. "forward deployed", "customer-facing engineering", "LLM prompting") — do not normalise or paraphrase

Parse the JSON output (or orchestrator extraction) to get `keywords` and `role_family`.

Display ALL extracted keywords to user (do not truncate):
```
Role family:  motorsport
Required:     Python, C++, data pipeline, telemetry, real-time, forward deployed,
              customer onboarding, LLM prompting, scalable solutions, ...
Nice to have: Kafka, MATLAB, F1 experience, ...
```

---

### Step 2 — Load experience data

Load all three files directly (no subprocess needed — read them as part of orchestrator context):

```
uv run --project "C:/Code/CV_CoverLetter_Generator_Agentic_Pipeline/job-pipeline" python - <<'EOF'
import json, sys
from pathlib import Path

store_path = Path(r"C:\Code\CV_crawl\.cv-harvest-store.json")
if not store_path.exists():
    print("ERROR: .cv-harvest-store.json not found. Run /cv-harvest first.", file=sys.stderr)
    sys.exit(1)

work_exp_path = Path(r"C:\Code\CV_crawl\.cv-work-experience.json")
if not work_exp_path.exists():
    print("ERROR: .cv-work-experience.json not found.", file=sys.stderr)
    sys.exit(1)

cache_path = Path(r"C:\Code\CV_crawl\.experience-cache.json")
store = json.loads(store_path.read_text(encoding="utf-8"))
work_exp = json.loads(work_exp_path.read_text(encoding="utf-8"))
cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
print(json.dumps({"store": store, "work_exp": work_exp, "cache": cache}))
EOF
```

---

### Step 2b — Project selection

Before running gap analysis, show the user a numbered list of projects from the store and ask which to exclude or flag as partial contribution:

```
Projects in your experience store:
  1. CV_CoverLetter_Generator_Agentic_Pipeline — Agentic CV & Cover Letter Pipeline
  2. aerodynamic_RAG__analyser — Aerodynamic Concept RAG Analyser
  3. fastAPI-design-project — Wing Aerodynamic Analyser API
  4. F1_StrategySimulator — F1 Race Strategy MARL Simulator
  5. TyreDataVisualiser — Tyre Data Visualiser (C# / SQL)
  6. DistributedSytemsCwk2 — Azure Serverless Distributed Pipeline
  7. tools — Job Search Intelligence Tooling
  8. Hand-Tracking-Using-Opencv — Real-Time Hand Tracking (CV)
  9. gra — Gryphon Racing AI — ROS System

Enter numbers to EXCLUDE (e.g. "3,7") or flag as PARTIAL ("p2,p9"), or press Enter to use all:
```

Parse the user's response and save to `C:\Code\CV_crawl\.cv-apply-project-selections.json`:

```json
{
  "excluded": ["fastAPI-design-project"],
  "partial": ["gra"]
}
```

Pass exclusions and partial flags to the CV Writer with these instructions:
- Excluded projects: do not use, do not generate bullets for them
- Partial projects: include but add "(partial contribution)" caveat to the project header and do not overstate ownership in bullets

---

### Step 3 — Gap analysis (two passes)

**Pass A — Existing gap questions** (from the experience store):

For each project in `experience_store["projects"]`:
- Collect all bullets where `gap_question` is not null AND `question_id` NOT already in `experience_cache`
- Filter to bullets where at least one `keyword` in `keywords_matched` overlaps with the JD's `required` or `nice_to_have` keywords
- Surface ALL matching questions — do not limit count

**Pass B — Missing keyword coverage**:

For each keyword in `keywords["required"]`:
- Check if any bullet in the experience store already covers it (keyword in `keywords_matched`)
- Check if any cached answer covers it (key contains the keyword)
- If not covered: generate an ad-hoc question:
  `"Do you have any experience with [keyword]? If so, describe briefly — it will be incorporated into your CV."`
- Assign key: `ad_hoc_{keyword}_{job_id}`

Combine Pass A + Pass B into a flat ordered list of questions.
If the list is empty, skip to Step 5.

---

### Step 4 — Interactive gap-fill

For each question in the list, present:
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Question [N of M]:
[question text]

Why this matters: "[keyword]" is required by [company] — [role title]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Your answer (or press Enter to skip):
```

After each answer:
- If answered: save to `experience_cache[question_id] = {"answer": text, "job_id": job_id, "ts": utcnow}`
- If skipped: save `experience_cache[question_id] = {"answer": null, "skipped": true}`
- Write `experience_cache` back to `.experience-cache.json` immediately after each answer

```python
import json
from datetime import datetime
from pathlib import Path

def save_cache(cache: dict) -> None:
    Path(r"C:\Code\CV_crawl\.experience-cache.json").write_text(
        json.dumps(cache, indent=2, ensure_ascii=False), encoding="utf-8"
    )
```

---

### Step 5 — CV Writer sub-agent

Spawn a CV Writer sub-agent with the following context:

```
You are a senior technical CV writer for a motorsport/software engineering graduate.
Apply the cv-bullet-writer skill rules to every bullet you produce.

CANDIDATE: Branson Tay — CS student at University of Leeds.

=== WORK EXPERIENCE BANK ===
[Full JSON of work_exp from .cv-work-experience.json]

For work experience sections, ONLY use facts from the WORK EXPERIENCE BANK above.
Do not infer, extrapolate, or add anything beyond what is listed in verified_facts.
Do not contradict anything in the explicit_not lists.
If insufficient verified facts exist to fill a slot with a quality bullet, leave the
slot text as "ASK_USER: [describe what fact is needed]" — do not invent content.

=== JOB TARGET ===
Company: [company]
Role: [job_title]
Role family: [role_family]
Required keywords: [keywords.required joined by ", "]
Nice-to-have: [keywords.nice_to_have joined by ", "]

=== EXPERIENCE STORE ===
[Full JSON of experience_store]

=== CACHED ANSWERS ===
[Full JSON of experience_cache — only include entries where answer is not null]

=== TEMPLATE SLOT CONSTRAINTS ===
You must assign bullets only to valid slots — counts are FIXED and cannot be changed:

work_experience:
  Jaguar TCS Racing: 13 bullet slots
  Republic of Singapore Navy: 5 bullet slots
  Travelindr: 3 bullet slots

technical_projects:
  Formula Student Lap Time Simulator: 3 bullet slots
  Radiator Thermal Management Simulator: 2 bullet slots
  2D CFD Formula Student Radiator Optimisation: 2 bullet slots
  Formula Student ICE Data Acquisition: 2 bullet slots
  Formula Student EV Battery Management: 2 bullet slots

You may HIDE any technical project (sets it to blank). To show a DIFFERENT project
in a slot, use header_swaps to rename the title + fill bullets with new content.
Work experience sections cannot be hidden or renamed.

=== BULLET RULES ===
- Target 100–108 characters per bullet, HARD MAX 115 characters
- No colons or semicolons anywhere in bullet text
- Start each bullet with a strong past-tense action verb
- Mirror JD keyword language exactly where evidence supports it
- Use exact JD phrases verbatim wherever evidence supports them. If the JD says "forward deployed", "customer onboarding", "LLM prompting", or "scalable solutions", embed those exact strings in bullets. Do not paraphrase a JD phrase into synonyms unless the evidence genuinely doesn't support the original wording.
- Incorporate cached answers where relevant — weave them into bullet phrasing
- Never invent skills not evidenced in the experience store, work experience bank, or cached answers
- No banned phrases: "fast-paced", "passionate about", "team player", "good", "bad", 
"leveraged synergies", "results-driven", "dynamic team"
- QUALITY GATE: Every bullet must either (a) hit a JD keyword from the required or
  nice-to-have lists, OR (b) state a concrete outcome or metric. A bullet that only
  restates the job title or describes presence in a team adds no value and must be
  rewritten or replaced. If you cannot produce a quality bullet for a slot, output
  "ASK_USER: [fact needed]" rather than a weak bullet.
- Use British English throughout (optimised, analysed, modelling, etc.)
- VERB DEDUPLICATION: Across all approved_bullets, no past-tense action verb may start more than 2 bullets. Count first-word verb occurrences before finalising output; replace 3rd+ occurrences with a strong synonym verb that fits the bullet's meaning.

=== OUTPUT FORMAT ===
For every `technical_projects` header_swap, append ` | ` followed by 3–6 key technologies drawn from the project's `tech_tags`. Format exactly as: `Title | Tech1, Tech2, Tech3`. No trailing pipe, no extra spaces around `|`.

Produce a single JSON object:

{
  "job_id": [job_id],
  "user_id": 1,
  "session_timestamp": "[ISO UTC timestamp]",
  "hidden_projects": ["project name if hidden", ...],
  "header_swaps": [
    {"section": "technical_projects", "subsection": "Formula Student Lap Time Simulator",
     "header_xpath_index": 0, "text": "New Project Title | Python, React, TypeScript"}
  ],
  "approved_bullets": [
    {
      "slot_index": 0,
      "section": "work_experience",
      "subsection": "Jaguar TCS Racing",
      "text": "Bullet text here, 100-110 chars",
      "source": "rephrasing",
      "rephrase_generation": 0
    },
    ...fill ALL non-hidden slots...
  ]
}

IMPORTANT: Fill every slot in every non-hidden subsection.
If a project is not hidden, all its bullet slots must have approved_bullets entries.
```

---

### Step 5b — Bullet length validation gate

After receiving the CV Writer's JSON output, write it to a temp file and validate:

```
uv run --project "C:/Code/CV_CoverLetter_Generator_Agentic_Pipeline/job-pipeline" python - <<'EOF'
import json, sys
sys.path.insert(0, r"C:\Code\CV_CoverLetter_Generator_Agentic_Pipeline\job-pipeline")
from agent.validators import validate_bullet_text

selections = json.loads(open(r"C:\Code\CV_crawl\.cv-apply-selections-tmp.json", encoding="utf-8").read())
hard_failures, soft_warnings = [], []

for bullet in selections["approved_bullets"]:
    is_valid, error, warnings = validate_bullet_text(bullet["text"])
    if not is_valid:
        hard_failures.append({"bullet": bullet, "error": error})
    for w in warnings:
        soft_warnings.append({"bullet": bullet, "warning": w})

print(json.dumps({"hard_failures": hard_failures, "soft_warnings": soft_warnings}))
EOF
```

Write the CV Writer JSON to `C:\Code\CV_crawl\.cv-apply-selections-tmp.json` before running.

If `hard_failures` is non-empty:
- Send back to CV Writer: `"Shorten these bullets to ≤ 100 chars:\n" + json.dumps(hard_failures)`
- CV Writer returns shortened versions only (not a full regeneration)
- Retry up to 2 times
- If still failing after 2 retries, report to user and ask whether to proceed

**Verb deduplication scan** (run after bullet-length check passes):

Count the first word (lowercased) of each bullet in `approved_bullets`. If any verb appears ≥ 3 times:
- Collect all bullets where that verb is the first word (sorted by slot_index)
- Keep the first 2 occurrences unchanged
- Flag the 3rd+ occurrence(s) as verb-dedup violations
- Send back to CV Writer: `"VERB DEDUP: The following bullets start with an overused verb. Replace the first word with a strong synonym that fits the bullet meaning:\n" + json.dumps(violations)`
- CV Writer returns only the affected bullets with new opening verbs
- Max 1 retry for verb dedup
- If still violating after 1 retry, proceed anyway

Only proceed to Step 6 when all bullets pass with no hard errors.

---

### Step 6 — Render DOCX

```
uv run --project "C:/Code/CV_CoverLetter_Generator_Agentic_Pipeline/job-pipeline" python - <<'EOF'
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
EOF
```

Write `{"job_id": ..., "company": ..., "job_title": ...}` to `C:\Code\CV_crawl\.cv-apply-meta-tmp.json` before running.
Capture stdout as the DOCX path.

---

### Step 6.5 — Visual line-wrap check (docx skill)

**a. Convert rendered DOCX → images:**
```
uv run --project "C:/Code/CV_CoverLetter_Generator_Agentic_Pipeline/job-pipeline" python -c "
import comtypes.client, os, fitz, sys

docx_path = sys.argv[1]
pdf_path = docx_path.replace('.docx', '_check.pdf')

word = comtypes.client.CreateObject('Word.Application')
word.Visible = False
doc = word.Documents.Open(os.path.abspath(docx_path))
doc.SaveAs(os.path.abspath(pdf_path), FileFormat=17)
doc.Close()
word.Quit()

pdf = fitz.open(pdf_path)
for i, page in enumerate(pdf):
    pix = page.get_pixmap(matrix=fitz.Matrix(150/72, 150/72))
    pix.save(f'cv_check_page_{i+1}.jpg')
pdf.close()
print(pdf_path)
" "<docx_path>"
```
This produces `cv_check_page_1.jpg`, `cv_check_page_2.jpg`, etc. in the current working directory.

**b. Visual inspection:**
Read every page image with the Read tool. Visually identify any bullet point that spills onto a second line.
Record each overflow as: `{slot_index, section, subsection, current_text}`.

**c. If overflowing bullets found — shorten and re-render:**
- Apply cv-bullet-writer skill rules to shorten each overflowing bullet:
  `"Shorten to fit one printed line — wraps visually. Target ≤ 105 chars. All other bullet rules still apply."`
- Patch `.cv-apply-selections-tmp.json` with rephrased bullets
- Re-run Step 6 render (same output DOCX path)
- Repeat steps a–b. **Max 3 iterations.**
- After 3 iterations, surface still-wrapping bullets to user and ask whether to proceed.

**d. Cleanup:**
Delete the temporary images and PDF generated in this step.
(The final PDF is produced from the approved DOCX in Step 8.)

---

### Step 7 — Show summary + approval loop

Display:
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CV PREVIEW — [company] | [job_title]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

JAGUAR TCS RACING (13 bullets)
  • [first line of bullet 1]
  • [first line of bullet 2]
  ... [show all]

REPUBLIC OF SINGAPORE NAVY (5 bullets)
  • ...

[technical projects shown/hidden with titles]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
KEYWORD COVERAGE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Required keywords:
  ✓ Python          → Jaguar bullet 3, Project bullet 1
  ✓ data pipeline   → Jaguar bullet 7
  ⚠ C++             → NOT COVERED
  ✓ telemetry       → Jaguar bullet 2, Jaguar bullet 5
  ...

Nice-to-have keywords:
  ✓ MATLAB          → Jaguar bullet 4
  ⚠ Kafka           → NOT COVERED
  ...

[N of M required keywords covered]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[A]pprove  |  [F]eedback: describe changes
```

Build the keyword coverage table by scanning all approved_bullets' text for each keyword string (case-insensitive). For each required keyword, show the first 1–2 matching bullets (section + slot_index). Mark uncovered required keywords with ⚠.

If user types `A` → proceed to Step 8.

If user types feedback (e.g. "Remove the Travelindr section, make bullet 3 of Jaguar focus more on real-time systems"):
- Re-run CV Writer with the original context PLUS: `"REFINEMENT CONSTRAINT: [user feedback]"`
- Re-run Step 5b validation
- Re-render (Step 6)
- Re-show summary (Step 7)
- Maximum 3 refinement cycles. After 3, proceed regardless.

---

### Step 8 — PDF output + DB update

1. Convert to PDF:
```
uv run --project "C:/Code/CV_CoverLetter_Generator_Agentic_Pipeline/job-pipeline" \
    python "C:/Code/CV_crawl/tools/docx_to_pdf.py" "<docx_path>"
```

2. Update job status in DB:
```
uv run --project "C:/Code/CV_CoverLetter_Generator_Agentic_Pipeline/job-pipeline" python -c "
import psycopg2, os, json, sys
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(r'C:/Code/CV_crawl') / '.env')

meta      = json.loads(open(r'C:/Code/CV_crawl/.cv-apply-meta-tmp.json', encoding='utf-8').read())
docx_path = sys.argv[1]
pdf_path  = sys.argv[2]

conn = psycopg2.connect(os.environ['DATABASE_URL'])
with conn.cursor() as cur:
    cur.execute(
        \"UPDATE job_status SET status = 'cv_generated', status_updated = %s WHERE job_id = %s\",
        (datetime.utcnow(), meta['job_id'])
    )
    cur.execute(\"SELECT id FROM application_packs WHERE job_id = %s\", (meta['job_id'],))
    row = cur.fetchone()
    if row:
        cur.execute(
            \"UPDATE application_packs SET cv_path = %s WHERE job_id = %s\",
            (docx_path, meta['job_id'])
        )
    else:
        cur.execute(
            \"INSERT INTO application_packs (job_id, cv_path, cover_letter_path, created_at) VALUES (%s, %s, %s, %s)\",
            (meta['job_id'], docx_path, None, datetime.utcnow())
        )
conn.commit()
conn.close()
print('DB updated: status -> cv_generated')
" "<docx_path>" "<pdf_path>"
```

3. Print final summary:
```
✓ CV generated for [company] — [job_title]
  DOCX: [out_path]
  PDF:  [pdf_path]
  Keywords covered: [N of M required keywords]
```

---

### Step 9 — Cover letter (optional)

After printing the Step 8 summary, prompt:

```
Generate cover letter? [Y/n]:
```

**If user enters `n` or `N`** — skip this step entirely. `cover_letter_path` remains
null in the DB (set in Step 8 above).

**If user enters `Y`, `y`, or presses Enter (default Yes)** — invoke the
`cover-letter-generation` skill. All required context is already in session:
- `company`, `job_title`, `job_id`
- `keywords` (from Step 1)
- `work_exp`, `experience_cache` (from Step 2)
- `docx_path`, `pdf_path` (from Steps 6 and 8)

The cover-letter-generation skill handles all sub-steps internally (address loading,
story selection, writing, humanisation, approval loop, render, DB update). Follow
its instructions from Step 1 through Step 9.
