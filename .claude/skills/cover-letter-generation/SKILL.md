# cover-letter-generation skill

Generates a tailored, human-sounding cover letter for a specific job application.
Called from `/cv-apply` after the CV is approved.

---

## Architecture principles

This skill is designed around four properties:

**1. Narrow sub-tasks** - each step has one job and one output. No step does scoring
AND writing AND validating. This keeps each LLM call focused and accurate.

**2. Token efficiency** - no sub-agent receives context it does not use. Story facts
are loaded from `story-bank.json` on demand; only selected stories are passed to
writers. Style rules are included only in writing prompts.

**3. Context-rot immunity** - no step relies on in-memory session variables from the
calling conversation. All shared state is written to `.cv-cl-checkpoint.json` after
each step and read back fresh at the start of the next. Long conversations can never
corrupt state.

**4. Self-healing and self-improving:**
  - Every sub-agent call is wrapped in a retry loop (max 2 retries) with schema
    validation. If output fails validation, the error is fed back explicitly.
  - The quality gate auto-detects and auto-fixes style violations before human review.
  - A persistent `past-errors` log tracks recurring writing and layout failures and
    the fixes that worked.
  - After each approved letter, a retrospective entry is appended to
    `.cv-cl-improvement-log.jsonl`. The story scorer reads the last 10 entries to
    bias future selections based on past success.

---

## Checkpoint file

Path: `C:\Code\CV_crawl\.cv-cl-checkpoint.json`

This is the single source of truth. Every step reads it at start and writes it at end.
Its schema tracks progress so the skill can resume from any point.

```json
{
  "schema_version": 2,
  "step_completed": 3,
  "job_id": "...",
  "company": "...",
  "job_title": "...",
  "keywords": { "required": [], "nice_to_have": [] },
  "profile": {
    "name": "", "address_line1": "", "address_line2": "",
    "address_line3": "", "email": ""
  },
  "company_address": "",
  "story_scores": { "jaguar_matlab_tyre": 0, "jaguar_alkamel": 0, "jaguar_youtube_cnn": 0, "gryphon_gps": 0, "travelindr_mvp": 0 },
  "selected_stories": [],
  "draft": { "INTRO": "", "PARA1": "", "PARA2": "", "PARA3": "", "CONCLUSION": "" },
  "validation_report": { "violations": [], "clean": true },
  "humanised": { "INTRO": "", "PARA1": "", "PARA2": "", "PARA3": "", "CONCLUSION": "" },
  "refinement_cycle": 0,
  "feedback_history": [],
  "cl_docx_path": "",
  "cl_pdf_path": ""
}
```

**Checkpoint update rule:** after each step completes, update `step_completed` to that
step number and merge the step's outputs into the checkpoint. Write to disk before
proceeding.

---

## Sub-agent retry wrapper

Apply this wrapper to every sub-agent call in this skill:

```
MAX_RETRIES = 2
attempt = 0

while attempt <= MAX_RETRIES:
    output = call_sub_agent(prompt)
    validation_error = validate_output_schema(output, expected_schema)

    if validation_error is None:
        break  <- success

    attempt += 1
    if attempt > MAX_RETRIES:
        STOP. Write { "step_completed": N, "error": "Sub-agent failed schema validation after 3 attempts: [error]" } to checkpoint.
        Tell user: "Step N failed after 3 attempts. See checkpoint for details. You can retry by typing /resume."
        Halt this skill.

    <- append to prompt for next attempt:
    "Your previous output failed validation with this error: [validation_error]
     Regenerate from scratch. The output MUST match the required format exactly."
```

---

## Story bank reference

Stories are stored in:
`C:\Code\CV_crawl\.claude\skills\cover-letter-generation\story-bank.json`

Each story has: `label`, `title`, `themes`, `keyword_heuristics`, `facts`, `do_not_say`.

**DO NOT load all stories at once into any sub-agent prompt.** Load story metadata
(label, title, themes, keyword_heuristics) for scoring. Load only the `facts` and
`do_not_say` for selected stories when writing paragraphs.

---

## Style rules reference

Included verbatim into all writing sub-agent prompts and the quality gate.

```
STYLE RULES - apply without exception:
- First person throughout. Never say "Branson did X" - say "I did X".
- Tell a story, don't sell. Write as if explaining what happened. The story sells itself.
- British English: optimised, analysed, modelling, recognise.
- Balanced tone: confident but not arrogant.
- FORBIDDEN WORDS: passionate, leverage, synergy, dynamic,
  fast-paced, team player, results-driven, excited to, highly motivated, dedicated,
  meticulous, diligent.
- 1-2 ideas per sentence maximum.
- Concrete over vague: name the tool, the team, the outcome.
- Varied sentence length: mix short punchy sentences with longer contextual ones.
- Active voice: "I built" not "a tool was built by me".
- FORBIDDEN OPENINGS: "I am writing to apply for", "at this exciting opportunity",
  "I would be a great fit", "I look forward to hearing from you at your earliest convenience".
- No em-dashes (-) or en-dashes (-) in body text. Rewrite the sentence.
- No colons in body text. Restructure the sentence.
- No semicolons in body text. Split into two sentences.
- No comma-separated lists ("x, y and z"). Weave naturally or use separate sentences.
- No self-evaluation adjectives. Show behaviour instead of claiming the trait.
- FORBIDDEN PARAGRAPH OPENERS: sentences that judge the significance of your own past
  work ("the most useful X I built", "some of the most important work I did",
  "some of the most useful work I did at [company]"). Open with a skill, approach,
  or concrete observation instead. Preferred patterns: "My approach to X",
  "My [skill] in X comes from", "Building [thing] taught me",
  "At [company], the challenge was", "The principle that shaped this work was".
```

---

## Step 0 - Resume detection

**Before anything else**, check if `C:\Code\CV_crawl\.cv-cl-checkpoint.json` exists.

If it exists, read it and check `job_id` against the current `job_id` from the caller.

- **Same job_id AND `step_completed` >= 1:** Print:
  ```
  -----------------------------------------
  RESUME DETECTED - [company] | [job_title]
  Last completed step: [step_completed]
  -----------------------------------------
  [R]esume from step [N+1]  |  [S]tart fresh
  -----------------------------------------
  ```
  If `R`: skip all completed steps and jump to step `step_completed + 1`, loading
  state from checkpoint.
  If `S`: delete checkpoint and start from Step 1.

- **Different job_id or no checkpoint:** proceed to Step 1.

---

## Step 1 - Context bootstrap

**Purpose:** validate caller-supplied context and write the initial checkpoint.

Read from caller session (these must exist; halt with a clear error if missing):
- `company`, `job_title`, `job_id`
- `keywords["required"]`, `keywords["nice_to_have"]`

Validate: `required` must be a non-empty list. If empty, print a warning but continue.

Write initial checkpoint:
```json
{
  "schema_version": 2,
  "step_completed": 1,
  "job_id": "[job_id]",
  "company": "[company]",
  "job_title": "[job_title]",
  "keywords": { "required": [...], "nice_to_have": [...] }
}
```

Token budgeting: trim `required` to the 12 most relevant keywords, `nice_to_have` to
8. If either list exceeds these limits, keep the most specific/technical terms and
drop generic ones like "communication" or "team player".

---

## Step 2 - Load sender profile

**Purpose:** load or collect the candidate's address. One task, one file.

Read `C:\Code\CV_crawl\.cv-profile.json`.

If it does not exist or is missing any required field, prompt the user **once**:
```
Sender details needed for letter header:
  Full name:
  Address line 1 (street):
  Address line 2 (building/area):
  Address line 3 (city, postcode):
  Email:
```
Save their responses to `.cv-profile.json`.

Do not re-prompt on subsequent runs if the file is complete and valid.

Update checkpoint: add `"profile": {...}` and set `"step_completed": 2`.

---

## Step 3 - Company address

**Purpose:** a single optional input. Keep it separate so it cannot block other steps.

Ask:
```
Company address for letter header (press Enter to skip):
```

Accept blank. Update checkpoint: add `"company_address": "[value or empty string]"`,
set `"step_completed": 3`.

---

## Step 4 - Story scoring

**Purpose:** pick the 3 best stories using keyword matching. **Do NOT load full story
facts here.** Load only metadata.

### 4a. Load improvement log bias

Read `C:\Code\CV_crawl\.cv-cl-improvement-log.jsonl`.
If it exists, load the last 10 entries.

For each story label, compute a `history_penalty`:
```
history_penalty(story) = -0.5 x (mean refinement_cycles for entries where this story
                                  was used AND role keywords overlap > 50% with current)
```
A story that consistently needed 2 refinement cycles for similar roles scores -1.0.
A story never needing refinement scores 0.0. A story never used scores 0.0.

### 4b. Score each story

For each story in story-bank.json, compute:
```
base_score = (2 x count of required keywords matching keyword_heuristics)
           + (1 x count of nice_to_have keywords matching keyword_heuristics)
final_score = base_score + history_penalty(story)
```

Matching is case-insensitive substring match between each keyword and the heuristics
list.

### 4c. Select top 3

Select the 3 highest `final_score` stories. On a tie, prefer stories covering
**distinct keyword clusters** (check that the matched keywords do not heavily overlap
between two tied stories).

Record scores and selection:
```json
{
  "story_scores": { "jaguar_matlab_tyre": 6.0, "jaguar_alkamel": 4.5, ... },
  "selected_stories": ["jaguar_matlab_tyre", "jaguar_alkamel", "gryphon_gps"]
}
```

### 4d. Present to user

```
-------------------------------------------------------------
STORY SELECTION - [company] | [job_title]
-------------------------------------------------------------
Para 1:  [story title]  (score: [N])
         Themes: [themes]
         Matches: [matched required keywords]

Para 2:  [story title]  (score: [N])
         Themes: [themes]
         Matches: [matched required keywords]

Para 3:  [story title]  (score: [N])
         Themes: [themes]
         Matches: [matched required keywords]

[A]ccept  |  [S]wap: e.g. "swap para2 for travelindr_mvp"
-------------------------------------------------------------
```

If swap: apply it, confirm the new selection, re-present.
Update checkpoint: set `"step_completed": 4`.

---

## Step 5 - Sequenced drafting

**Purpose:** write intro and conclusion first, then write body paragraphs modularly
using intro/conclusion as context.

### Before firing: load only selected stories' facts

From `story-bank.json`, for each of the 3 selected story labels, load:
- `facts` array (joined as a bullet list)
- `do_not_say` array

Do not load themes, keyword_heuristics, or any other stories.

### 5A - Intro + Conclusion sub-agent (run first)

Spawn a single sub-agent with this prompt:

```
You are a cover letter writer. Write ONLY the intro and conclusion for a cover letter.
Output ONLY the two labelled sections - no other text.

=== CANDIDATE ===
Name: [name]
Background: Mechanical engineering diploma + computer science. Formula E placement at
Jaguar TCS Racing. Co-founder of Travelindr. Leeds university Formula Student team.

=== JOB TARGET ===
Company: [company]
Role: [job_title]
Date: [today's date, e.g. "16th March 2026"]

=== SELECTED STORIES (HEADLINES ONLY) ===
[story title 1], [story title 2], [story title 3]

=== REQUIRED KEYWORDS ===
[keywords.required - max 12 items]

=== INTRO INSTRUCTIONS ===
3-4 sentences.
- State who you are and what you offer at the intersection of your skills.
- You may name the company if it flows naturally. Never name the specific role title -
  express intent through what you want to contribute, not by attaching a job label.
  If mentioning the company would feel like a formal declaration of intent, leave it out
  and let the conclusion carry that weight.
- End with a concrete signal of why THIS company - not a generic claim. Reference
  something specific about their work, mission, or technical scope.
- MUST NOT open with "I am writing to apply for".
- MUST NOT contain any sentence that reads like a formal application statement,
  e.g. "I am applying for the X role at Y." This sounds stiff and adds nothing -
  the reader already knows you are applying.

=== CONCLUSION INSTRUCTIONS ===
2-3 sentences.
- State what you specifically want to contribute in this role.
- Reference the role's technical scope or something concrete about the company.
- Must NOT repeat the intro.
- Must NOT use "I look forward to hearing from you."

=== STYLE RULES ===
[insert style rules verbatim from Style rules reference above]

=== OUTPUT FORMAT ===
[INTRO]
<text>

[CONCLUSION]
<text>
```

**Expected output schema:** string containing both `[INTRO]` and `[CONCLUSION]`
labels on their own lines, each followed by non-empty text. Apply retry wrapper.

Create a compact framing summary for downstream body generation:
- `candidate_thesis` (one sentence)
- `company_hook` (one sentence)
- `intended_contribution` (one sentence)

### 5B - Paragraph sub-agent (run for Para1, Para2, Para3)

For each paragraph N (1, 2, 3), spawn a sub-agent with this prompt:

```
You are a cover letter paragraph writer. Write ONE body paragraph for a cover letter.
Follow every rule exactly. Output ONLY the labelled paragraph - no other text.

=== JOB TARGET ===
Company: [company]
Role: [job_title]

=== INTRO/CONCLUSION CONTEXT ===
[INTRO]
[intro text]

[CONCLUSION]
[conclusion text]

=== FRAMING SUMMARY ===
- Candidate thesis: [candidate_thesis]
- Company hook: [company_hook]
- Intended contribution: [intended_contribution]

=== REQUIRED KEYWORDS - weave in where the story genuinely supports them ===
[keywords.required - max 12 items]

=== STORY FACTS - use only these facts, do not invent others ===
[facts for selected story N - bullet list]

=== DO NOT SAY ===
[do_not_say for selected story N - bullet list]

=== PARAGRAPH STRUCTURE - follow this spine in order ===
1. Opening statement: one sentence establishing a skill, approach, or perspective.
   FORBIDDEN opener patterns: "the most useful/important X I built/did", "some of the
   most [superlative] work I did", any sentence that opens by judging the significance
   of your own past work.
   PREFERRED patterns: "My approach to X...", "My [skill] in X comes from...",
   "Building [thing] taught me...", "At [company], the challenge was...",
   "The principle that shaped this work was..."
   Para1 MUST open: "Firstly, ..."
   Para2 MUST open: "Secondly, ..."
   Para3 MUST open: "Lastly, ..."
2. Context: 1-2 sentences - what was the situation, what problem existed.
3. Actions: specifically what you did - name the tool, method, or collaborator.
4. Reasoning: why you made key decisions.
5. Learning / impact: what changed or was produced.
6. Link to company: one sentence connecting this story to why it matters for THIS
   role at [company]. Must feel like a conclusion, not a sales pitch.

=== STYLE RULES ===
[insert style rules verbatim from Style rules reference above]

=== OUTPUT FORMAT - output ONLY this, no preamble, no notes ===
[PARA[N]]
<paragraph text>
```

**Expected output schema:** string starting with `[PARA1]`, `[PARA2]`, or `[PARA3]`
on its own line, followed by non-empty paragraph text. Apply retry wrapper.

### 5C - Assemble draft

After all four sub-agents complete, extract each labelled section and assemble:
```json
"draft": {
  "INTRO": "...",
  "PARA1": "...",
  "PARA2": "...",
  "PARA3": "...",
  "CONCLUSION": "..."
}
```

Validate all 5 keys are non-empty. If any is empty or missing, re-run only the
failed sub-agent (not all four). Update checkpoint with draft, set `"step_completed": 5`.

---

## Step 6 - Quality gate (auto-heal)

**Purpose:** catch and fix style violations before human review. No LLM needed for
most rules - apply as deterministic text transforms.

For each section in `draft` (INTRO, PARA1, PARA2, PARA3, CONCLUSION), apply each
check in order. Track all violations.

### Checks and auto-fixes

| Check | Detection | Auto-fix |
|---|---|---|
| Forbidden words | Case-insensitive match against forbidden words list | Flag for rewrite (cannot reliably auto-fix meaning - flag for human or targeted LLM rewrite) |
| Em-dash / en-dash | `-` or `-` in text | Split sentence at dash; join with `. ` where natural |
| Semicolons | `;` in text | Replace with `. ` |
| Colon in body | `:` not in a ratio or time context | Rewrite clause: drop colon and restructure if simple; flag if complex |
| Sentence > 40 words | Word count per sentence | Flag the sentence for human or LLM split |
| "I am writing to apply" anywhere | Exact phrase match | Flag - cannot auto-fix without changing meaning |
| Comma-separated list of 3+ items | `(.+), (.+) and (.+)` | Flag for manual rewrite |
| Third-person references to Branson | `Branson [verb]` | Replace with `I [verb]` |

For forbidden-word violations and complex rewrites that cannot be deterministically
fixed, spawn a single targeted **fix-up sub-agent**:

```
The following cover letter sections contain style violations. Rewrite ONLY the
flagged sentences. Do not change any other text.

=== VIOLATIONS ===
[list each violation: section, sentence, rule broken, suggested approach]

=== SECTIONS TO FIX ===
[only the sections containing violations]

=== STYLE RULES ===
[insert style rules verbatim]

=== OUTPUT FORMAT ===
Return ONLY the fixed sections with labels:
[INTRO]
<corrected text or original if no changes>

[PARA1]
... etc.
```

Apply retry wrapper. Merge fixed sections back into draft.

### Validation report

```json
"validation_report": {
  "violations": [
    { "section": "PARA2", "rule": "semicolon", "original": "...", "fixed": "..." }
  ],
  "auto_fixed": 2,
  "flagged_for_rewrite": 1,
  "clean": true
}
```

Set `"clean": true` if no violations remain after fixes.
Print a compact summary:
```
Quality gate: [N] issues found -> [N] auto-fixed, [N] rewritten. All clear.
```

Update checkpoint with `validation_report` and validated draft (replace `draft` with
the post-gate version). Set `"step_completed": 6`.

---

## Step 7 - Humanisation pass

**Purpose:** improve prose quality. Process one section at a time to stay focused.

Work through INTRO, PARA1, PARA2, PARA3, CONCLUSION in order. For each, apply these
rules and track changes:

1. **Remove repetition** - if the same noun or phrase appears within 3 sentences of
   itself in the same section, rephrase one occurrence.
2. **Remove throat-clearing openers** - delete or rephrase: "It is worth noting that",
   "I would like to highlight", "I am pleased to say", "As such", "Thus", "Hence",
   "Furthermore", "Moreover" when they open a sentence.
3. **Vary paragraph openers** - if any two adjacent body paragraphs both start with "I",
   rephrase one to open with an action phrase, a context phrase, or a time reference.
4. **Natural connectives** - replace "In addition," or "Furthermore," with "Alongside
   this," or just start a new sentence. Replace "Moreover," with "On top of this," or
   remove entirely.
5. **Self-evaluation adjectives** - if any survived the quality gate, remove here.

Apply these rules directly as the orchestrator (no sub-agent for this step). These are
deterministic or near-deterministic transforms.

For each section, output:
```
[INTRO - 2 changes]
<revised text>

[PARA1 - no changes]
<original text>
```

Build `humanised` dict. Update checkpoint: add `"humanised": {...}`, set
`"step_completed": 7`.

---

## Step 8 - Preview and approval loop

Display the full letter:

```
-------------------------------------------------------------
COVER LETTER PREVIEW - [company] | [job_title]
-------------------------------------------------------------

[name]
[address_line1]
[address_line2]
[address_line3]
[email]

[company_name]
[company_address - omit line if blank]

[date]

Dear Hiring Manager,

[INTRO]

[PARA1]

[PARA2]

[PARA3]

[CONCLUSION]

Yours Faithfully,
[name]

-------------------------------------------------------------
[A]pprove  |  [F]eedback: describe what to change and where
-------------------------------------------------------------
```

### Approval

If `A`: proceed to Step 9.

### Feedback - targeted refinement

If user provides feedback:

1. **Parse which sections are affected.** If feedback names a specific paragraph
   (e.g. "para2 should focus more on ownership", "the intro is too generic"), only
   that section is regenerated. If feedback is letter-wide, regenerate all.

2. **Spawn a targeted refinement sub-agent for each affected section only:**
   ```
   Rewrite [SECTION] of this cover letter based on the feedback below.
   Do not change any other sections.

   === CURRENT TEXT ===
   [current humanised text of this section]

   === FEEDBACK ===
   [user feedback]

   === STORY FACTS (if a body para) ===
   [facts for that paragraph's story - only if PARA1/2/3]

   === STYLE RULES ===
   [insert style rules verbatim]

   === OUTPUT FORMAT ===
   [SECTION]
   <revised text>
   ```

3. Apply the quality gate (Step 6) to the revised sections only.
4. Apply humanisation rules (Step 7) to the revised sections only.
5. Merge back into `humanised`, update checkpoint with new feedback entry:
   ```json
   "feedback_history": [
     { "cycle": 1, "feedback": "...", "sections_affected": ["PARA2"] }
   ]
   ```
6. Increment `refinement_cycle`. Re-display preview.

7. **Maximum 3 refinement cycles.** After the 3rd cycle:
   ```
   Maximum refinement cycles reached - proceeding with the current draft.
   ```
   Proceed to Step 9 automatically.

Update checkpoint: set `"step_completed": 8`.

---

## Step 9 - Render DOCX -> PDF -> 1-page check -> DB

### 9a. Build the render payload

```json
{
  "name":            "[profile.name]",
  "address_line1":   "[profile.address_line1]",
  "address_line2":   "[profile.address_line2]",
  "address_line3":   "[profile.address_line3]",
  "email":           "[profile.email]",
  "company_name":    "[company]",
  "company_address": "[company_address, may be empty string]",
  "date":            "[today formatted as e.g. '16th March 2026']",
  "salutation":      "Dear Hiring Manager,",
  "intro":           "[humanised.INTRO]",
  "para1":           "[humanised.PARA1]",
  "para2":           "[humanised.PARA2]",
  "para3":           "[humanised.PARA3]",
  "conclusion":      "[humanised.CONCLUSION]",
  "company":         "[re.sub(r'[^\\w\\-]', '_', company)]",
  "role":            "[first 30 chars of re.sub(r'[^\\w\\-]', '_', job_title)]"
}
```

Write to `C:\Code\CV_crawl\.cv-cover-letter-tmp.json`.

### 9b. Render DOCX

```
uv run --project "C:/Code/CV_CoverLetter_Generator_Agentic_Pipeline/job-pipeline" \
    python "C:/Code/CV_crawl/tools/render_cover_letter.py" \
    "C:/Code/CV_crawl/.cv-cover-letter-tmp.json"
```

Capture stdout as `cl_docx_path`.

### 9c. Convert to PDF

```
uv run --project "C:/Code/CV_CoverLetter_Generator_Agentic_Pipeline/job-pipeline" \
    python "C:/Code/CV_crawl/tools/docx_to_pdf.py" "[cl_docx_path]"
```

Capture stdout as `cl_pdf_path`.

### 9d. Mandatory one-page enforcement (DOCX + PDF)

The cover letter **MUST** be one page.

Run:

```
uv run --project "C:/Code/CV_CoverLetter_Generator_Agentic_Pipeline/job-pipeline" \
    python "C:/Code/CV_crawl/tools/enforce_one_page_cover_letter.py" \
    "C:/Code/CV_crawl/.cv-cover-letter-tmp.json"
```

This script:
- renders DOCX with layout presets (`default`, `tight`, `tighter`)
- converts each to PDF
- checks final page count using `tools/check_pdf_pages.py`
- succeeds only when page count is exactly 1

Parse stdout JSON:
```json
{
  "docx_path": "...",
  "pdf_path": "...",
  "pages": 1,
  "layout_preset": "tight"
}
```

Set `cl_docx_path` and `cl_pdf_path` from this JSON output.

If the script fails (still >1 page):
- append an entry to `.cv-cl-past-errors.jsonl`
- trigger targeted refinement to reduce verbosity, then rerun Step 9d
- maximum 2 layout retries + 1 text-compression retry

### 9e. Update database

```python
uv run --project "C:/Code/CV_CoverLetter_Generator_Agentic_Pipeline/job-pipeline" python -c "
import psycopg2, os, sys, json
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(r'C:/Code/CV_crawl') / '.env')

meta    = json.loads(open(r'C:/Code/CV_crawl/.cv-apply-meta-tmp.json', encoding='utf-8').read())
cl_docx = sys.argv[1]
cl_pdf  = sys.argv[2]

conn = psycopg2.connect(os.environ['DATABASE_URL'])
with conn.cursor() as cur:
    cur.execute('SELECT id FROM application_packs WHERE job_id = %s', (meta['job_id'],))
    row = cur.fetchone()
    if row:
        cur.execute(
            'UPDATE application_packs SET cover_letter_path = %s WHERE job_id = %s',
            (cl_pdf, meta['job_id'])
        )
    else:
        cur.execute(
            'INSERT INTO application_packs (job_id, cv_path, cover_letter_path, created_at) VALUES (%s, %s, %s, %s)',
            (meta['job_id'], None, cl_pdf, datetime.utcnow())
        )
conn.commit()
conn.close()
print('DB updated: cover_letter_path set')
" "[cl_docx_path]" "[cl_pdf_path]"
```

On DB failure: print a warning and continue. The files already exist on disk.
```
[!] DB update failed: [error]. Files are saved - update DB manually if needed.
  INSERT: job_id=[job_id], cover_letter_path=[cl_pdf_path]
```

### 9f. Update checkpoint and print summary

Update checkpoint: `"cl_docx_path"`, `"cl_pdf_path"`, `"step_completed": 9`.

```
[x] Cover letter generated - [company] | [job_title]
  DOCX: [cl_docx_path]
  PDF:  [cl_pdf_path]
```

---

## Step 10 - Retrospective + past-errors memory

**Purpose:** capture what worked for future story scoring.

Append one JSON line to `C:\Code\CV_crawl\.cv-cl-improvement-log.jsonl`:

```json
{
  "timestamp": "[ISO 8601 UTC]",
  "job_id": "[job_id]",
  "company": "[company]",
  "job_title": "[job_title]",
  "keywords_required": [...],
  "stories_used": ["[story1_label]", "[story2_label]", "[story3_label]"],
  "story_scores": { ... },
  "refinement_cycles": [checkpoint.refinement_cycle],
  "feedback_history": [checkpoint.feedback_history],
  "sections_refined": [unique list of sections that received feedback],
  "auto_fixes_applied": [checkpoint.validation_report.auto_fixed],
  "cl_pdf_path": "[cl_pdf_path]"
}
```

If there were writing-rule failures, page-overflow failures, or repeated refinements,
append one JSON line per failure to `C:\Code\CV_crawl\.cv-cl-past-errors.jsonl`:

```json
{
  "timestamp": "[ISO 8601 UTC]",
  "job_id": "[job_id]",
  "company": "[company]",
  "job_title": "[job_title]",
  "error_type": "layout_overflow|style_violation|schema_retry_failure",
  "step": "[step number]",
  "section": "[INTRO|PARA1|PARA2|PARA3|CONCLUSION|layout]",
  "trigger": "[rule/page-count reason]",
  "fix_applied": "[what was changed]",
  "outcome": "resolved|unresolved"
}
```

Print:
```
Retrospective logged. Improvement log now has [N] entries.
Past-errors log updated.
```

Delete the temporary files:
- `.cv-cl-checkpoint.json` (clear for next run)
- `.cv-cover-letter-tmp.json`

Do NOT delete `.cv-cl-improvement-log.jsonl` - this persists across all runs.

---

## Error recovery guide

If the skill halts with an error marker in the checkpoint:

1. Read the checkpoint's `"error"` field for the failure description.
2. If the issue is a missing file or env var, fix it and type `/resume`.
3. If the issue is a malformed sub-agent output after 3 retries, the step will be
   re-run fresh on `/resume`.
4. `/resume` always reads step_completed from checkpoint and restarts from
   `step_completed + 1`.

---

## Context variables from caller

These must be available in session when this skill is invoked. They are only read at
Step 1 and immediately written to checkpoint; they are not used again directly.

| Variable | Source |
|---|---|
| `company` | Selected job row |
| `job_title` | Selected job row |
| `job_id` | Selected job row |
| `keywords` | JD extraction step in cv-apply |
