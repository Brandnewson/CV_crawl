# /cv-apply - Tailored CV Generator

Takes a job from your PostgreSQL pipeline, runs gap-fill Q&A, writes a CV tailored
to that job, and produces a DOCX + PDF in `{REPO_ROOT}\output\`.

---

## Paths (resolved at runtime from `user_config.yaml`)

| Asset | Path |
|---|---|
| Experience store | `{REPO_ROOT}\.cv-harvest-store.json` |
| Work experience bank | `{REPO_ROOT}\.cv-work-experience.json` |
| Experience cache | `{REPO_ROOT}\.experience-cache.json` |
| Evidence pack tmp | `{REPO_ROOT}\.tmp\.cv-apply-evidence-pack-tmp.json` |
| Slot plan tmp | `{REPO_ROOT}\.tmp\.cv-apply-slot-plan-tmp.json` |
| Coverage plan tmp | `{REPO_ROOT}\.tmp\.cv-apply-coverage-plan-tmp.json` |
| Coverage review tmp | `{REPO_ROOT}\.tmp\.cv-apply-coverage-review-tmp.json` |
| Checkpoint | `{REPO_ROOT}\.tmp\.cv-apply-checkpoint.json` |
| Fact patches log | `{REPO_ROOT}\.cv-fact-patches.jsonl` |
| Run metrics log | `{REPO_ROOT}\.cv-apply-run-metrics.jsonl` |
| CV template (2-page) | `{REPO_ROOT}\profile\cv_template.docx` |
| Template map (2-page) | `{REPO_ROOT}\profile\template_map.json` |
| CV template (1-page) | `{REPO_ROOT}\profile\cv_template_1page.docx` |
| Template map (1-page) | `{REPO_ROOT}\profile\template_map_1page.json` |
| Automation lessons | `{REPO_ROOT}\LESSONS.md` |
| Temp dir | `{REPO_ROOT}\.tmp\` |
| Output dir | `{CV_OUTPUT_DIR}\<Company>\` |
| Pipeline code | `{REPO_ROOT}\` |
| uv project | `{REPO_ROOT}\` |

## Python runtime

All Python must be run via uv so the pipeline's venv (psycopg2, lxml, pydantic, etc.) is active:

```
uv run --project "{REPO_ROOT}" python <script> <args>
```

Never call bare `python` - always prefix with `uv run --project "{REPO_ROOT}"`.

---

## Checkpointed runner (preferred)

Use the hybrid stage runner as the primary execution engine:

```
uv run --project "{REPO_ROOT}" \
    python "{REPO_ROOT}/tools/cv_apply_runner.py" --resume
```

Rules:
- `.cv-apply-checkpoint.json` is the single orchestration source of truth.
- Each stage writes artifacts + `step_completed` before moving forward.
- Retry policy is max 2 retries per stage output validation.
- Resume always starts from `step_completed + 1`.
- If a stage reports `blocked`, collect requested input/artifact and rerun with `--resume`.

Runner stage graph:
1. job_select
2. jd_extract
3. source_load
4. project_select
5. gap_detect
6. gap_normalize
7. evidence_select
8. slot_plan
9. coverage_plan
10. coverage_review
11. draft_work_experience
12. draft_technical_projects
13. assemble
14. validate_deterministic
15. render_docx_pdf
16. layout_gate_2pages (expected-page + wrap gate)
17. preview_feedback
18. feedback_classify
19. fact_patch_apply
20. targeted_regen
21. persist_db
22. cover_letter_handoff

---
## ORCHESTRATOR - run this sequence

### Step -1 — Detect repo root and load user config

Run:
```
git -C "<current working directory>" rev-parse --show-toplevel
```

Store the output as `REPO_ROOT`. Use `{REPO_ROOT}` everywhere a path is needed in this command.

Read `{REPO_ROOT}/user_config.yaml` (if it exists) and store values as:
- `CV_OUTPUT_DIR` = cv_output_dir field (or `{REPO_ROOT}/cv-outputs`)

If `user_config.yaml` does not exist, tell the user to run `/cv-setup` first and stop.

---

### Step 0 - Query ranked jobs from DB

Before executing any shell/Python snippet, read `{REPO_ROOT}\LESSONS.md`
and apply relevant rules (especially L001 for bash quoting).
If a recurring automation failure appears, append a new lesson entry with
symptom, root cause, and safe pattern.

Track `current_offset` across pages (start at 0). Run (let it fail loudly if DB is unavailable - no fallbacks):

```
uv run --project "{REPO_ROOT}" \
    python "{REPO_ROOT}/tools/query_jobs.py" --min-score 0.65 --status new --limit 20 --offset {current_offset} --include-recent
```

If the command exits non-zero, surface the error message verbatim and stop. Do not offer
any fallback or alternative - the DB must be running and populated before using this command.

Parse the JSON output - it is a dict with keys `new_jobs` and `recent_jobs`.

Display the new jobs like this (use the `fit_summary` field for the summary line, truncated
to ~200 chars; use `location` for the city line; use `job_url` for the link):

```
--------------------------------------------------------------
NEW JOBS  (page {current_offset // 20 + 1})
--------------------------------------------------------------
 1  0.90  CHAOS Industries - Forward Deployed Engineer - Software
          Defence AI startup - deploy sensing/ML products to field customers.
          London, UK
          https://jobs.chaosind.com/fde-software

 2  0.90  Procore Technologies - Forward Deployed Engineer (Datagrid)
          Construction SaaS - onsite customer data pipeline integration work.
          New York, US
          https://...
...
```

Then display the recent runs section (jobs from `recent_jobs`, using `cv_generated_at` for the date):

```
--------------------------------------------------------------
RECENT RUNS  (select to regenerate or compare CVs)
--------------------------------------------------------------
R1  Applied Intuition - Forward Deployed Engineer  [run 2026-03-12]
    Autonomous vehicles startup - technical deployment to car-maker customers.
    https://...

R2  HappyRobot - Forward Deployed Engineer  [run 2026-03-11]
    AI logistics startup - real-time freight negotiation platform deployment.
    https://...
```

If `recent_jobs` is empty, omit the RECENT RUNS section entirely.

Ask the user: **"Which job? Enter number, R1-R5 to rerun, or N for next 20:"**

If the user enters `N`, increment `current_offset` by 20, re-run the query with the new offset,
and re-display (RECENT RUNS section is omitted on page 2+; it always reflects the 5 most recent runs).

When the user selects an R-number, load that job from `recent_jobs` and proceed exactly
as for a new job - all subsequent steps are identical. This allows regenerating or
refining a CV for a job already in the pipeline.

After job selection, ask:
**"CV length for this run- Enter 1 or 2 pages:"**

Set `cv_length_pages` to `1` or `2` and persist this in `{REPO_ROOT}\.tmp\.cv-apply-meta-tmp.json`
alongside `job_id`, `company`, and `job_title`. Also persist a run-level `cv_variant_id`
for controlled same-job rerun variation.

**Pre-run cleanup**: After the user selects a job, check whether temp files from a
different job are present. Run:

```python
import json, os
from pathlib import Path

checkpoint = Path(r"{REPO_ROOT}\.tmp\.cv-apply-checkpoint.json")
selected_job_id = SELECTED_JOB_ID  # replace with the actual job_id integer
to_delete = [
    r"{REPO_ROOT}\.tmp\.cv-apply-evidence-pack-tmp.json",
    r"{REPO_ROOT}\.tmp\.cv-apply-slot-plan-tmp.json",
    r"{REPO_ROOT}\.tmp\.cv-apply-coverage-plan-tmp.json",
    r"{REPO_ROOT}\.tmp\.cv-apply-coverage-review-tmp.json",
    r"{REPO_ROOT}\.tmp\.cv-apply-jd-keywords-tmp.json",
    r"{REPO_ROOT}\.tmp\.cv-apply-project-selections.json",
    r"{REPO_ROOT}\.tmp\.cv-apply-selections-tmp.json",
    r"{REPO_ROOT}\.tmp\.cv-apply-meta-tmp.json",
    r"{REPO_ROOT}\.tmp\.cv-apply-context-tmp.json",
    r"{REPO_ROOT}\.tmp\.cv-apply-jd-tmp.txt",
]
if checkpoint.exists():
    try:
        ckpt = json.loads(checkpoint.read_text())
        if ckpt.get("job_id") != selected_job_id:
            for f in to_delete:
                try:
                    os.remove(f)
                except FileNotFoundError:
                    pass
            print(f"Cleaned up temp files from previous run (job {ckpt.get('job_id')}).")
    except Exception:
        pass
```

(Replace `SELECTED_JOB_ID` with the actual numeric job_id from the user's selection.)

---

### Step 1 - Load and clean JD

1. Load the selected job's `description` field from the query results.
2. **JD keyword cache check** — before running extraction, check for a cached file:
   `{REPO_ROOT}\.jd-keywords-cache\{job_id}.json`
   If it exists and is non-empty, load it as `keywords` and `role_family`, print
   `Keywords loaded from cache (job {job_id}) — skipping extraction.`, display the
   keywords to the user, and skip straight to Step 2. Do NOT re-extract.
3. If no cache hit: write the raw JD description to `{REPO_ROOT}\.tmp\.cv-apply-jd-tmp.txt`.
4. Extract keywords via the safe wrapper script (no inline Python):
```
uv run --project "{REPO_ROOT}" \
    python "{REPO_ROOT}/tools/extract_jd_keywords.py" \
    --jd-path "{REPO_ROOT}/.tmp/.cv-apply-jd-tmp.txt" \
    --job-title "<job_title>" \
    --out "{REPO_ROOT}/.tmp/.cv-apply-jd-keywords-tmp.json" \
    --cache-out "{REPO_ROOT}/.jd-keywords-cache/<job_id>.json"
```

Parse the JSON output to get `keywords` and `role_family`.

Output contract:

```json
{
  "keywords": {
    "required": ["..."],
    "nice_to_have": ["..."],
    "phrase_inventory": {
      "required_phrases": ["..."],
      "nice_to_have_phrases": ["..."],
      "day_to_day_phrases": ["..."],
      "responsibility_phrases": ["..."]
    }
  },
  "role_family": "..."
}
```

Display ALL extracted keywords to user (do not truncate):
```
Role family:  motorsport
Required:     Python, C++, data pipeline, telemetry, real-time, forward deployed,
              customer onboarding, LLM prompting, scalable solutions, ...
Nice to have: Kafka, MATLAB, F1 experience, ...
```

---

### Step 2 - Load experience data

Load all three files directly (no subprocess needed - read them as part of orchestrator context):

```
uv run --project "{REPO_ROOT}" \
    python "{REPO_ROOT}/tools/load_cv_sources.py" \
    --store-path "{REPO_ROOT}/.cv-harvest-store.json" \
    --work-exp-path "{REPO_ROOT}/.cv-work-experience.json" \
    --cache-path "{REPO_ROOT}/.experience-cache.json"
```

---

### Step 2b - Project selection

Before running gap analysis, show the user a numbered list of projects from the store and ask which to exclude or flag as partial contribution:

```
Projects in your experience store:
  1. CV_CoverLetter_Generator_Agentic_Pipeline - Agentic CV & Cover Letter Pipeline
  2. aerodynamic_RAG__analyser - Aerodynamic Concept RAG Analyser
  3. fastAPI-design-project - Wing Aerodynamic Analyser API
  4. F1_StrategySimulator - F1 Race Strategy MARL Simulator
  5. TyreDataVisualiser - Tyre Data Visualiser (C# / SQL)
  6. DistributedSytemsCwk2 - Azure Serverless Distributed Pipeline
  7. tools - Job Search Intelligence Tooling
  8. Hand-Tracking-Using-Opencv - Real-Time Hand Tracking (CV)
  9. gra - Gryphon Racing AI - ROS System

Enter numbers to EXCLUDE (e.g. "3,7") or flag as PARTIAL ("p2,p9"), or press Enter to use all:
```

Parse the user's response and save to `{REPO_ROOT}\.tmp\.cv-apply-project-selections.json`:

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

### Step 3 - Gap analysis (two passes)

**Pass A - Existing gap questions** (from the experience store):

For each project in `experience_store["projects"]`:
- Collect all bullets where `gap_question` is not null AND `question_id` NOT already in `experience_cache`
- Filter to bullets where at least one `keyword` in `keywords_matched` overlaps with the JD's `required` or `nice_to_have` keywords
- Surface ALL matching questions - do not limit count

**Pass B - Missing keyword coverage**:

For each keyword in `keywords["required"]`:
- Check if any bullet in the experience store already covers it (keyword in `keywords_matched`)
- Check if any cached answer text covers it (keyword appears in `answer`, case-insensitive)
- If not covered: generate an ad-hoc question:
  `"Do you have any experience with [keyword]- If so, describe briefly - it will be incorporated into your CV."`
- Assign key: `ad_hoc_{keyword}_{job_id}`

Combine Pass A + Pass B into a flat ordered list of questions.
If the list is empty, skip to Step 4.5.

---

### Step 4 - Interactive gap-fill

For each question in the list, present:
```
----------------------------------------------------------
Question [N of M]:
[question text]

Why this matters: "[keyword]" is required by [company] - [role title]
----------------------------------------------------------
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
    Path(r"{REPO_ROOT}\.experience-cache.json").write_text(
        json.dumps(cache, indent=2, ensure_ascii=False), encoding="utf-8"
    )
```

---

### Step 4.5 - Evidence select (claim graph extraction)

Build diversity-first claim units and subsection evidence packs before any writing:

```
uv run --project "{REPO_ROOT}" \
    python "{REPO_ROOT}/tools/evidence_select.py" \
    --work-exp "{REPO_ROOT}/.cv-work-experience.json" \
    --store "{REPO_ROOT}/.cv-harvest-store.json" \
    --keywords "{REPO_ROOT}/.tmp/.cv-apply-jd-keywords-tmp.json" \
    --project-selections "{REPO_ROOT}/.tmp/.cv-apply-project-selections.json" \
    --template-map "<resolved_template_map_path>" \
    --out "{REPO_ROOT}/.tmp/.cv-apply-evidence-pack-tmp.json"
```

Output contract (`.cv-apply-evidence-pack-tmp.json`):
- `claim_units`: atomic claims with `claim_id`, `action`, `system_component`, `method_tool`, `outcome_impact`, `keyword_links`, `confidence`, `source_ref`
- `similarity_groups`: near-duplicate claim clusters
- `evidence_packs`: per subsection `subsection_id`, `slot_count`, `allowed_fact_ids`, `disallowed_claims`, `keyword_targets`, `priority_facts`, `partial_contribution_flag`

`blocked_claim_ids` / `disallowed_claims` must include duplicate-cluster claims and explicit-not risk claims.

---

### Step 4.6 - Slot plan (intent planner, not text planner)

Generate bullet intent cards and project/header assignments from the evidence pack:

```
uv run --project "{REPO_ROOT}" \
    python "{REPO_ROOT}/tools/slot_plan.py" \
    --evidence "{REPO_ROOT}/.tmp/.cv-apply-evidence-pack-tmp.json" \
    --template-map "<resolved_template_map_path>" \
    --out "{REPO_ROOT}/.tmp/.cv-apply-slot-plan-tmp.json"
```

Output contract (`.cv-apply-slot-plan-tmp.json`):
- `hidden_projects`, `header_swaps`
- `bullet_intent_cards` with:
  `intent_id`, `section`, `subsection`, `slot_index`, `intent_type`,
  `primary_claim_id`, `secondary_claim_ids`, `keyword_target`,
  `must_include`, `must_avoid`
- `writer_brief_cards` (minimal evidence per slot)
- `insufficiency_questions`, `is_sufficient`

Hard diversity constraints in this stage:
- do not reuse the same `primary_claim_id` within a subsection
- do not repeat the same `intent_type + similarity_group` combo
- reject near-duplicate intent cards before drafting
- normalise subsection identities to template-map keys (`...Simulator`/`...System` names must match exactly)

---

### Step 4.7 - Hard insufficiency gate (ask user before drafting)

Read `.cv-apply-slot-plan-tmp.json`.

If `is_sufficient` is false, DO NOT call CV Writer yet.
Ask each question in `insufficiency_questions` and persist answers to `.experience-cache.json` using:
- `question_id` as key
- `{ "answer": text, "job_id": job_id, "ts": utcnow, "source": "slot_gap" }`

When all insufficiency questions are handled:
1. Re-run Step 4.5
2. Re-run Step 4.6
3. Continue only when `is_sufficient` is true

This is a hard gate: paraphrase fallback is not allowed.

---

### Step 4.8 - Coverage plan (explicit vs implicit allocation)

Run:
```
uv run --project "{REPO_ROOT}" \
    python "{REPO_ROOT}/tools/coverage_plan.py" \
    --slot-plan "{REPO_ROOT}/.tmp/.cv-apply-slot-plan-tmp.json" \
    --jd-keywords "{REPO_ROOT}/.tmp/.cv-apply-jd-keywords-tmp.json" \
    --out "{REPO_ROOT}/.tmp/.cv-apply-slot-plan-tmp.json" \
    --report-out "{REPO_ROOT}/.tmp/.cv-apply-coverage-plan-tmp.json"
```

Rules:
- At least 50% of slots must be `coverage_mode=explicit`.
- Explicit slots prioritize required terms, then nice-to-have terms and phrase inventory.
- Writer consumes `coverage_mode` + `keyword_target` from writer brief cards.

---

### Step 4.9 - Coverage review gate (mandatory before drafting)

Read `{REPO_ROOT}\.tmp\.cv-apply-coverage-plan-tmp.json` and show:
- uncovered required terms
- uncovered nice-to-have terms
- support evidence cards suggested for each uncovered term

Ask user whether to:
- accept uncovered terms for this run, or
- provide additional facts / request reallocation.

Persist acknowledgement to:
`{REPO_ROOT}\.tmp\.cv-apply-coverage-review-tmp.json`
with at least:
```json
{"status":"approved","notes":"..."}
```

If user provides new facts, add:
```json
"cache_updates": {
  "ad_hoc_<keyword>_<job_id>": "new fact answer"
}
```
Then re-run from `evidence_select` so evidence/slot/coverage plans are refreshed.

Do not draft until review file is approved.

---

### Step 5 - CV Writer sub-agent

**Before spawning the sub-agent**, extract the three keys the CV Writer needs from the
slot plan (this avoids sending the full 64KB file into the sub-agent's context):

```python
import json
from pathlib import Path

sp = json.loads(Path(r"{REPO_ROOT}\.tmp\.cv-apply-slot-plan-tmp.json").read_text())
writer_context = {
    "hidden_projects": sp["hidden_projects"],
    "header_swaps": sp["header_swaps"],
    "writer_brief_cards": sp["writer_brief_cards"],
}
print(json.dumps(writer_context, indent=2))
```

Capture the output as `writer_context_json`. Then spawn a CV Writer sub-agent with the
following compact context, substituting `[WRITER_CONTEXT_JSON]` with the captured output:

```
You are a senior technical CV writer for a motorsport/software engineering graduate.
Apply the cv-bullet-writer skill rules to every bullet you produce.

CANDIDATE: Branson Tay - CS student at University of Leeds.

=== JOB TARGET ===
Company: [company]
Role: [job_title]
Role family: [role_family]
Required keywords: [keywords.required joined by ", "]
Nice-to-have: [keywords.nice_to_have joined by ", "]

=== SLOT PLAN (MANDATORY SOURCE OF TRUTH) ===
[WRITER_CONTEXT_JSON]

Each writer_brief_card provides:
- intent_id
- section, subsection, slot_index
- intent_type
- keyword_target
- primary_claim (claim_id, text, source_ref)
- secondary_claims
- must_include
- must_avoid

You must realise each card as one bullet. Do not invent new cards.

=== BULLET RULES ===
- HARD MAX 120 characters per bullet
- Optimise around 110 characters, preferring under over over-limit
- Never brute-force truncation/cutoff to meet layout
- No colons or semicolons anywhere in bullet text
- Start each bullet with a strong past-tense action verb
- Mirror JD keyword language exactly where the intent evidence supports it
- If `keyword_target` is non-empty for a card, include that phrase verbatim (case-insensitive) in the bullet text
- Never introduce claims outside primary_claim or secondary_claims for the same intent_id
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
Produce a single JSON object:

{
  "job_id": [job_id],
  "user_id": 1,
  "session_timestamp": "[ISO UTC timestamp]",
  "hidden_projects": [copy exactly from slot plan],
  "header_swaps": [copy exactly from slot plan],
  "approved_bullets": [
    {
      "slot_index": 0,
      "section": "work_experience",
      "subsection": "Jaguar TCS Racing",
      "text": "Bullet text here, optimised near 110 chars (<=120 hard max)",
      "intent_id": "intent_work_jaguar_tcs_racing_0",
      "provenance": {
        "primary_claim_id": "work_jaguar_tcs_racing_0",
        "secondary_claim_ids": ["work_jaguar_tcs_racing_1"],
        "source_ref": {"source": ".cv-work-experience.json", "org": "Jaguar TCS Racing", "fact_index": 0}
      },
      "source": "rephrasing",
      "rephrase_generation": 0
    },
    ...fill ALL non-hidden slots...
  ]
}

IMPORTANT: Fill every slot in every non-hidden subsection.
If a project is not hidden, all its bullet slots must have approved_bullets entries.
Every approved bullet must include intent_id and provenance.
```

---

### Step 5b - Deterministic validation gate (length + verb + anti-redundancy)

After receiving the CV Writer's JSON output, write it to `{REPO_ROOT}\.tmp\.cv-apply-selections-tmp.json`,
then run the canonical validator contract:

```
uv run --project "{REPO_ROOT}" \
    python "{REPO_ROOT}/tools/validate_cv_output.py" \
    --selections "{REPO_ROOT}/.tmp/.cv-apply-selections-tmp.json" \
    --slot-plan "{REPO_ROOT}/.tmp/.cv-apply-slot-plan-tmp.json" \
    --work-exp "{REPO_ROOT}/.cv-work-experience.json"
```

This single gate enforces:
- schema completeness
- slot fill completeness
- provenance presence
- explicit_not conflict checks
- style and banned phrase checks
- canonical bullet length contract (hard max 120)
- explicit-slot target inclusion + whole-CV explicit quota
- verb deduplication
- semantic anti-redundancy

If validator returns `ok: false`:
- Retry only `failed_bullets` using the same `intent_id` and same claim ids.
- Retry message to CV Writer:
  `"VALIDATION FAIL: regenerate only these bullets while preserving intent_id and provenance:\n" + json.dumps(failed_bullets)`
- Max 2 targeted retries.
- If still failing after 2 retries, invalidate only affected subsection intent cards and re-run Step 4.6 for those subsections.

Only proceed to Step 6 when `validate_cv_output.py` returns `ok: true`.

---

### Step 6 - Render DOCX

```
uv run --project "{REPO_ROOT}" \
    python "{REPO_ROOT}/render_cv.py" \
    --meta-path "{REPO_ROOT}/.tmp/.cv-apply-meta-tmp.json" \
    --selections-path "{REPO_ROOT}/.tmp/.cv-apply-selections-tmp.json" \
    --template-path "<resolved_template_path>" \
    --template-map-path "<resolved_template_map_path>" \
    --insert-page-break-before-technical-projects "<true_or_false>"
```

Write `{"job_id": ..., "company": ..., "job_title": ..., "cv_length_pages": 1|2}` to `{REPO_ROOT}\.tmp\.cv-apply-meta-tmp.json` before running.
Capture stdout as the DOCX path.

---

### Step 6.5 - Deterministic wrap optimization gate

`layout_gate_2pages` now performs:
- expected-page check
- PDF-based wrapped-bullet detection
- targeted wrapped-bullet rephrase retries (max retry budget), preserving:
  - `intent_id`
  - provenance
  - explicit `keyword_target`

No brute-force truncation or hard cutting is allowed in this gate.
If retries are exhausted, surface unresolved wrapped slots to user for targeted edits.

---

### Step 6.6 - CV content sanity check (bug detection)

Read the rendered DOCX using python-docx and run these checks before showing the user preview:

```python
import sys, re
from docx import Document
import json
from pathlib import Path

def normalise_for_check(text: str) -> str:
    """Strip zero-width spaces and other Word line-break hints before comparison."""
    return re.sub(r'[\u200b\u200c\u200d\ufeff]', '', text)

doc = Document("<docx_path>")
selections = json.loads(Path(r"{REPO_ROOT}\.tmp\.cv-apply-selections-tmp.json").read_text(encoding="utf-8"))

# Build expected state from selections
expected_headers = {s["subsection"]: s["text"] for s in selections.get("header_swaps", [])}
expected_bullets = {}
for b in selections["approved_bullets"]:
    key = (b["section"], b["subsection"])
    expected_bullets.setdefault(key, []).append(b["text"])

# Walk DOCX paragraphs and collect actual content
issues = []
current_section = None
actual_headers_found = []
actual_bullets_by_header = {}
current_header = None

for para in doc.paragraphs:
    t = para.text.strip()
    if not t:
        continue
    if "TECHNICAL PROJECTS" in t:
        current_section = "technical_projects"
    if "ADDITIONAL EXPERIENCE" in t:
        current_section = None

    if current_section == "technical_projects":
        # Heuristic: bold/heading-like paragraphs are project headers
        is_header = any(run.bold for run in para.runs if run.text.strip())
        if is_header and "|" in t:
            current_header = t
            actual_headers_found.append(t)
        elif current_header and t.startswith(tuple("ABCDEFGHIJKLMNOPQRSTUVWXYZ")):
            # Could be a bullet (starts with capital after header)
            actual_bullets_by_header.setdefault(current_header, []).append(t)

# Check 1: All header_swap names appear in the DOCX
docx_text_full = normalise_for_check("\n".join(p.text for p in doc.paragraphs))
for orig_sub, swapped_name in expected_headers.items():
    # Check the project name part (before the | tech stack)
    project_name = swapped_name.split("|")[0].strip()
    if project_name not in docx_text_full:
        issues.append(f"HEADER MISSING: '{project_name}' not found in rendered DOCX (header_swap may have failed)")

# Check 2: Bullet count per subsection
for (section, subsection), bullets in expected_bullets.items():
    for bullet_text in bullets:
        # Check first 60 chars of each bullet appears in DOCX
        snippet = bullet_text[:60]
        if snippet not in docx_text_full:
            issues.append(f"BULLET MISSING in DOCX: [{subsection}] '{snippet}...'")

# Check 3: No template placeholder text remains
template_placeholders = ["Formula Student Lap Time Simulator", "Radiator Thermal Management Simulator",
                         "2D CFD Formula Student Radiator", "Formula Student ICE Data Acquisition",
                         "Formula Student EV Battery Management"]
for placeholder in template_placeholders:
    if placeholder in docx_text_full:
        issues.append(f"TEMPLATE PLACEHOLDER REMAINS: '{placeholder}' — header_swap not applied")

if issues:
    print("SANITY CHECK FAILED:")
    for issue in issues:
        print(f"  - {issue}")
else:
    print("Sanity check PASSED - all headers swapped, all bullets present, no template placeholders")
```

If any issues are found, fix them before proceeding to Step 7. Do not show the user a CV with known rendering bugs.

---

### Step 7 - Show summary + approval loop

Display:
```
--------------------------------------------------------------
CV PREVIEW - [company] | [job_title]
--------------------------------------------------------------

JAGUAR TCS RACING (13 bullets)
  - [first line of bullet 1]
  - [first line of bullet 2]
  ... [show all]

REPUBLIC OF SINGAPORE NAVY (5 bullets)
  - ...

[TECHNICAL PROJECTS - for each non-hidden project, show title header and all bullets]

TECHNICAL PROJECTS
  F1 Race Strategy MARL Simulator | Python, PyTorch, ...
    - [bullet 0]
    - [bullet 1]
    - [bullet 2]

  Radiator Thermal Management Simulator | Matlab, ...
    - [bullet 0]

  ... [show all non-hidden projects with all their bullets, or "(hidden)" for hidden ones]

--------------------------------------------------------------
KEYWORD COVERAGE
--------------------------------------------------------------
Required keywords:
  [x] Python          -> Jaguar bullet 3, Project bullet 1
  [x] data pipeline   -> Jaguar bullet 7
  [!] C++             -> NOT COVERED
  [x] telemetry       -> Jaguar bullet 2, Jaguar bullet 5
  ...

Nice-to-have keywords:
  [x] MATLAB          -> Jaguar bullet 4
  [!] Kafka           -> NOT COVERED
  ...

[N of M required keywords covered]
--------------------------------------------------------------
[A]pprove  |  [F]eedback: describe changes
```

Build the keyword coverage table by scanning all approved_bullets' text for each keyword string (case-insensitive). For each required keyword, show the first 1-2 matching bullets (section + slot_index). Mark uncovered required keywords with [!].

If user types `A` -> proceed to Step 8.

If user types feedback (e.g. "Remove the Travelindr section, make bullet 3 of Jaguar focus more on real-time systems"):
- Classify feedback first:
  - factual correction / missing fact / overstated scope
  - stylistic or prioritisation feedback
- For stylistic or prioritisation feedback:
  - regenerate only affected bullets with same `intent_id` and same provenance claim ids
- For factual correction, missing fact, or overstated scope:
  - ask clarifying fact question if needed
  - update cache fact, re-run Step 4.5 and 4.6 for affected subsection, then regenerate only impacted bullets
- Re-run Step 5b validation
- Re-render (Step 6)
- Re-show summary (Step 7)
- Maximum 3 refinement cycles. After 3, proceed regardless.

---

### Step 8 - PDF output + DB update

1. Convert to PDF:
```
uv run --project "{REPO_ROOT}" \
    python "{REPO_ROOT}/tools/docx_to_pdf.py" "<docx_path>"
```

2. Update job status in DB:
```
uv run --project "{REPO_ROOT}" \
    python "{REPO_ROOT}/update_db.py" "<docx_path>" "<pdf_path>"
```

`update_db.py` persists CV paths using a schema-aware contract:
- Prefer `cv_docx_path` and `cv_pdf_path` columns when present
- Fallback to `cv_path` when legacy schema is in use
- Never overwrite `cover_letter_path` during CV generation

3. Track application in Excel tracker:
```
uv run --project "{REPO_ROOT}" \
    python "{REPO_ROOT}/tools/track_application.py" \
    --job-id "<job_id>" \
    --company "<company>" \
    --job-title "<job_title>" \
    --city "<location field from Step 0>" \
    --description "<first 2000 chars of raw JD description>" \
    --job-url "<job_url>"
```

4. Print final summary:
```
[x] CV generated for [company] - [job_title]
  DOCX: [out_path]
  PDF:  [pdf_path]
  Keywords covered: [N of M required keywords]
```

5. **Post-run cleanup** — delete large intermediate artifacts (evidence pack and slot plan
   are no longer needed; selections and meta are kept for Step 9 cover letter handoff):

```python
import os
for f in [
    r"{REPO_ROOT}\.tmp\.cv-apply-evidence-pack-tmp.json",
    r"{REPO_ROOT}\.tmp\.cv-apply-slot-plan-tmp.json",
    r"{REPO_ROOT}\.tmp\.cv-apply-coverage-plan-tmp.json",
    r"{REPO_ROOT}\.tmp\.cv-apply-coverage-review-tmp.json",
    r"{REPO_ROOT}\.tmp\.cv-apply-jd-keywords-tmp.json",
    r"{REPO_ROOT}\.tmp\.cv-apply-jd-tmp.txt",
]:
    try:
        os.remove(f)
    except FileNotFoundError:
        pass
```

---

### Step 9 - Cover letter (optional)

After printing the Step 8 summary, prompt:

```
Generate cover letter- [Y/n]:
```

**If user enters `n` or `N`** - skip this step entirely. `cover_letter_path` remains
null in the DB (set in Step 8 above).

**If user enters `Y`, `y`, or presses Enter (default Yes)** - invoke the
`cover-letter-generation` skill. All required context is already in session:
- `company`, `job_title`, `job_id`
- `keywords` (from Step 1)
- `work_exp`, `experience_cache` (from Step 2)
- `docx_path`, `pdf_path` (from Steps 6 and 8)

The cover-letter-generation skill handles all sub-steps internally (address loading,
story selection, writing, humanisation, approval loop, render, DB update). Follow
its instructions from Step 1 through Step 9.
