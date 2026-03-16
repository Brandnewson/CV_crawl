# cover-letter-generation skill

Generates a tailored, human-sounding cover letter for a specific job application.
Called from `/cv-apply` after the CV is approved. All job context (company, role,
keywords, work_exp, answered_cache) is already in session from cv-apply.

---

## Context expected from caller

The following variables are assumed to be in scope when this skill is invoked:

| Variable | Source |
|---|---|
| `company` | Selected job row from query_jobs |
| `job_title` | Selected job row |
| `job_id` | Selected job row |
| `keywords` | Extracted in Step 1 of cv-apply (`required`, `nice_to_have`) |
| `work_exp` | Loaded in Step 2 of cv-apply (`.cv-work-experience.json`) |
| `experience_cache` | Loaded in Step 2 of cv-apply (`.experience-cache.json`) |
| `docx_path` | CV DOCX path produced in Step 6 |
| `pdf_path` | CV PDF path produced in Step 8 |

---

## Style rules (apply throughout)

- **First person throughout** — never refer to the candidate in third
  person ("Branson developed..." is wrong; "I developed..." is correct)
- **Tell a story, don't sell** — write as if explaining what happened to someone, not
  pitching your qualities to a recruiter; the story sells itself
- **British English** — optimised, analysed, modelling, recognise, etc.
- **Balanced tone** — confident but not arrogant; enthusiastic but not gushing
- **No buzzwords** — never write: "passionate", "leverage", "synergy", "dynamic",
  "spearhead", "utilise", "fast-paced", "team player", "results-driven", "excited to"
- **1–2 ideas per sentence maximum** — long compound sentences obscure the point
- **Concrete over vague** — name the tool, the team, the outcome; avoid "I worked on X"
- **Varied sentence length** — mix short punchy sentences with longer contextual ones
- **Active voice** — "I built" not "a tool was built by me"
- **No clichés** — avoid: "I am writing to apply for", "at this exciting opportunity",
  "I would be a great fit", "I look forward to hearing from you at your earliest convenience"
- **No self-evaluation adjectives** — don't write "I am a highly motivated individual";
  show it through actions
- **No em-dashes or dashes** — never use — or – in body text; rewrite the sentence instead
- **No colons in body text** — restructure the sentence to avoid them
- **No semicolons in body text** — split into two sentences instead
- **No comma-separated lists** — never write "x, y and z" or "x, y, and z"; convert
  to separate sentences or weave naturally into prose
- **Paragraph structure for body paras (Firstly/Secondly/Lastly)**:
  - First sentence: simple statement of the theme in one clause ("Firstly, I thrive in
    ambiguous environments.")
  - Final sentence: a natural connection to the company that flows from the story, not
    a hard sales pivot; it should feel like a conclusion, not a pitch

---

## Letter format template

```
{name}
{address_line1}
{address_line2}
{address_line3}
{email}

{company_name}
{company_address}               ← optional; blank if user skips

{date}

Dear Hiring Manager,

[INTRO]   — 3–4 sentences. Who you are, what you offer, why this company specifically.
            Must NOT open with "I am writing to apply for". Name the role explicitly.

[PARA1]   — Story 1. Opens: "Firstly, ..."
[PARA2]   — Story 2. Opens: "Secondly, ..."
[PARA3]   — Story 3. Opens: "Lastly, ..."

[CONCLUSION] — 2–3 sentences. What you want to contribute in this specific role.
               Must NOT be generic. Reference something specific about the company
               or the role's technical scope.

Yours Faithfully,
{name}
```

### Body paragraph internal structure (Firstly/Secondly/Lastly)

Each story paragraph must follow this spine:

1. **Opening statement** — one sentence naming the theme (e.g. "I thrive in ambiguous,
   high-pressure environments")
2. **Context** — what the situation was, what problem existed (1–2 sentences)
3. **Actions** — specifically what you did, naming tools / methods / collaborators / technologies
4. **Reasoning** — why you made key decisions, what you were thinking
5. **Learning / impact** — what it produced, what changed, what you took away
6. **Link to company** — one sentence connecting this story to why it matters for this role

---

## Story bank (hardcoded — do not hallucinate new stories)

These are the five canonical stories available for selection. Each has a label, theme
tags, and the full narrative fact-set to draw from. Only use facts listed here.

---

### Story 1 — Jaguar MATLAB Tyre Tool

**Label:** `jaguar_matlab_tyre`
**Themes:** ambiguity, engineering-fundamentals, race-weekend-pressure, tool-building,
            multidisciplinary, performance, individual-initiative

**Facts:**
- Formula E Season 11 at Jaguar TCS Racing
- New tyres and four-wheel drive in attack mode introduced significant changes
- Team needed failsafe contingencies and wanted to unlock tyre performance
- Branson proposed and developed an in-house MATLAB tool on the race weekend itself
- Tool combined mechanical engineering (diploma background) with computer science skills
- Tool quantified the friction-brake energy required to raise tyre core temperatures
  without compromising battery strategy
- Validated the tool against race telemetry
- Presented findings to engineers — findings supported strategy decisions
- Contributed to holding off Porsche for P2 and securing a win at Shanghai Race 2
- Tool still in use at Jaguar today

**Do not say:** "I was passionate about", "I leveraged my skills", specific lap times
or energy figures you do not know.

---

### Story 2 — Jaguar Alkamel Timing Feed Converter

**Label:** `jaguar_alkamel`
**Themes:** cross-functional-collaboration, ownership, software-engineering, data-pipeline,
            scalability, stakeholder-management, Python

**Facts:**
- Jaguar TCS Racing internship; compact team — responsibilities overlapped
- Developed a Python-based data pipeline converting raw Alkamel Timing Feed data
  from a noSQL database into telemetry channels
- Sought feedback from Vehicle Performance Group to keep channels relevant
- Collaborated with software engineers on CI/CD architecture design
- Sought code reviews with senior engineers for OOP scalability (design patterns,
  modularity, extensive error handling)
- Aligned with race strategists to ensure outputs had direct race impact
- Started as a single Python file; grew into a fully functioning application
- Application still powering performance at Jaguar today

**Do not say:** specific API endpoints, database product names beyond "noSQL",
any performance metrics you do not know.

---

### Story 3 — Jaguar YouTube Clip CNN Extension

**Label:** `jaguar_youtube_cnn`
**Themes:** self-directed-learning, initiative, machine-learning, curiosity,
            cross-departmental, ownership, competitor-intelligence

**Facts:**
- Jaguar internship; regularly spoke with colleagues across departments
- Discovered an unused internal repository that identified onboard clips from YouTube
  livestreams
- Saw potential to repurpose and extend the tool
- Extended it to recognise competitor dashboard footage showing key data such as
  tyre pressures — needed by the tyre department
- Had no prior machine learning experience at the time
- Studied the fundamentals of the existing CNN classifier independently
- Sourced own training dataset
- Innovation significantly eased manual burden — freed engineers to focus on
  performance-critical tasks
- Demonstrates ownership and turning curiosity into tangible impact

**Do not say:** model accuracy figures, dataset size, specific frameworks beyond CNN
unless you know them.

---

### Story 4 — Gryphon Racing GPS Sensor Bridge

**Label:** `gryphon_gps`
**Themes:** cross-team-communication, stakeholder-alignment, data-architecture,
            systems-thinking, motorsport, collaboration

**Facts:**
- Leeds Gryphon Racing (university Formula Student team)
- New ECU and data acquisition system introduced a gap: electrics team unsure which
  sensors to install and what channel strategies to use; vehicle dynamics team
  struggling to validate design choices
- Branson identified the cross-team disconnect and facilitated a meeting between leads
- Communicated each team's requirements and constraints clearly
- Concluded that GPS sensors and wheel speed sensors were critical for correlating
  tyre models
- Defined sampling rates, logging strategies, and channel strategies together
- This provided vehicle dynamics team performance metrics in the format they needed
- Turned initial confusion into a key vehicle data architecture decision that will
  support performance for years

**Do not say:** specific sensor brands, car lap times, exact ECU model.

---

### Story 5 — Travelindr MVP / A-B Testing

**Label:** `travelindr_mvp`
**Themes:** product-thinking, customer-facing, iterative-development, entrepreneurship,
            agile, experimentation, user-research, leadership

**Facts:**
- Co-founder and CEO of Travelindr — a group travel-itinerary generator
- Built in a cross-functional team using Agile ways of working
- Ran focus-group discussions to inform product direction
- Created UI mockups to validate design decisions
- Conducted A/B testing and user interviews to iterate on features
- Set product strategy and direction
- Progressed the product to MVP stage
- Pitched to investors; secured incubation within a multinational company

**Do not say:** revenue figures, user counts, or any metric not listed above.
Do not imply Branson wrote production code — the role was executive/product.

---

## Orchestrator steps

### Step 1 — Load context

Read from session (already in memory from cv-apply):
- `company`, `job_title`, `job_id`
- `keywords["required"]`, `keywords["nice_to_have"]`
- `work_exp` (from `.cv-work-experience.json`)
- `experience_cache` (from `.experience-cache.json`)

No file reads needed at this step.

---

### Step 2 — Load sender address

Read `C:\Code\CV_crawl\.cv-profile.json`. If it does not exist or is missing required
fields, prompt the user **once** for:
- Full name
- Address line 1 (street)
- Address line 2 (city, postcode)
- Email

Then save to `.cv-profile.json`:
```json
{
  "name": "Branson Tay",
  "address_line1": "14 Samara West Mount",
  "address_line2": "59-61 Clarendon Road",
  "address_line3": "Leeds, West Yorkshire LS2 9NZ",
  "email": "bransontay@gmail.com"
}
```

Do not re-prompt on subsequent runs if file exists and is complete.

---

### Step 3 — Company address (optional)

Ask the user a single question:
```
Company address for letter header (press Enter to skip):
```

Accept blank — leave `company_address` as empty string if skipped.

---

### Step 4 — Story selection

**Map each story to JD themes:**

For each of the 5 stories in the story bank, score it against the required keywords:
- +2 for each required keyword thematically covered
- +1 for each nice-to-have keyword thematically covered

Theme → keyword mapping heuristics:
- `ambiguity / engineering-fundamentals / performance` → matches: "high-pressure",
  "technical", "engineering", "simulation", "telemetry", "performance"
- `cross-functional-collaboration / stakeholder-management` → matches: "cross-functional",
  "stakeholder", "collaboration", "customer", "teams", "business"
- `self-directed-learning / initiative / machine-learning` → matches: "ML", "machine
  learning", "self-starter", "initiative", "curiosity", "CNN", "computer vision"
- `cross-team-communication / data-architecture` → matches: "data pipeline", "architecture",
  "sensors", "systems", "communication", "motorsport"
- `product-thinking / customer-facing / iterative` → matches: "product", "customer",
  "agile", "A/B", "MVP", "user research", "iteration", "forward deployed"

Select the **3 highest-scoring** stories. In the event of a tie, prefer stories that
cover distinct keyword clusters (avoid two stories covering the same required keywords).

Present selection to user:
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STORY SELECTION for [company] — [job_title]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Para 1:  Story 1 — Jaguar MATLAB Tyre Tool
         Themes: ambiguity, engineering fundamentals, race-weekend pressure
         Covers: [list matched required keywords]

Para 2:  Story 2 — Jaguar Alkamel Timing Feed Converter
         Themes: cross-functional collaboration, Python, data pipeline
         Covers: [list matched required keywords]

Para 3:  Story 4 — Gryphon Racing GPS Sensor Bridge
         Themes: cross-team communication, data architecture
         Covers: [list matched required keywords]

[A]ccept  |  [S]wap: e.g. "swap para2 for story5"
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

If user types `A` — proceed.
If user types a swap instruction — apply it and confirm before proceeding.

---

### Step 5 — Cover Letter Writer sub-agent

Spawn a sub-agent (claude-sonnet) with this prompt:

```
You are a professional cover letter writer. Write a cover letter for the candidate
described below. Follow every instruction exactly — do not add sections, do not
change the label markers, do not summarise.

=== CANDIDATE PROFILE ===
Name: [name from .cv-profile.json]
Address: [full address]
Email: [email]

=== JOB TARGET ===
Company: [company]
Role: [job_title]
Date: [today's date formatted as e.g. "14th March 2026"]

=== REQUIRED KEYWORDS (weave naturally into the letter where evidence supports) ===
[keywords.required joined by ", "]

=== NICE-TO-HAVE KEYWORDS (use if a story naturally supports them) ===
[keywords.nice_to_have joined by ", "]

=== STORIES TO USE ===
Para 1 (opens "Firstly, ..."):
[Full fact-set for selected story 1 — copy from story bank above]

Para 2 (opens "Secondly, ..."):
[Full fact-set for selected story 2]

Para 3 (opens "Lastly, ..."):
[Full fact-set for selected story 3]

=== STYLE RULES ===
- British English throughout
- Balanced, confident tone — no buzzwords or clichés (see forbidden list below)
- 1–2 ideas per sentence maximum
- Concrete and specific — name the tool, the team, the outcome
- Active voice
- Vary sentence length — mix short punchy sentences with longer contextual ones
- Do NOT open with "I am writing to apply for..."
- Do NOT use: passionate, leverage, synergy, dynamic, spearhead, utilise, fast-paced,
  team player, results-driven, excited to, highly motivated individual

=== BODY PARAGRAPH STRUCTURE (apply to EACH of Para1/Para2/Para3) ===
1. Opening statement (one sentence naming the theme)
2. Context (1–2 sentences: what was the situation, what problem existed)
3. Actions (specifically what you did: tools, methods, collaborators)
4. Reasoning (why you made key decisions)
5. Learning / impact (what it produced, what changed)
6. Link to company (one sentence connecting this story to why it matters for THIS role at THIS company)

=== INTRO INSTRUCTIONS ===
3–4 sentences. State who you are and what you offer at the intersection of your
skills. Name the role explicitly. End with a clear signal of why this company
specifically — NOT a generic "I look forward to contributing". Reference something
concrete about the company's work or mission.

=== CONCLUSION INSTRUCTIONS ===
2–3 sentences. What you specifically want to contribute in this role. Reference the
role's technical scope or something specific about the company. Do not repeat the
intro. Do not use "I look forward to hearing from you."

=== OUTPUT FORMAT ===
Output ONLY the following labelled sections. No other text.

[INTRO]
<text>

[PARA1]
<text>

[PARA2]
<text>

[PARA3]
<text>

[CONCLUSION]
<text>
```

Parse the sub-agent output. Validate all 5 labels are present. If any label is missing,
ask the sub-agent to regenerate only the missing sections.

---

### Step 6 — Humanisation pass

The orchestrator applies this pass directly to the draft (no sub-agent). For each
paragraph in order, apply these rules and show a before/after diff only if changes
were made:

**Humanisation rules:**
1. **Remove repetition** — if the same noun or phrase appears within 3 sentences of
   itself in the same paragraph, rephrase one occurrence
2. **Remove pompous qualifiers** — delete or rephrase: "It is worth noting that",
   "I would like to highlight", "I am pleased to say", "As such", "Thus", "Hence",
   "Furthermore", "Moreover" when used as throat-clearing openers
3. **Break run-on sentences** — any sentence over 40 words should be split into two
4. **Vary paragraph openers** — if two consecutive paragraphs start with "I", rephrase
   one to start with an action, a context phrase, or the company name
5. **Natural connectives only** — replace "In addition," or "Furthermore," with
   "Alongside this," or just start a new sentence; replace "Moreover," with "On top
   of this," or remove entirely
6. **Remove self-evaluation adjectives** — delete: "highly motivated", "dedicated",
   "passionate", "meticulous", "diligent" when applied to self; replace by showing
   the behaviour instead

Print the final humanised version of each paragraph with label headers:
```
[INTRO — humanised]
...

[PARA1 — humanised]
...
```

If a paragraph required no changes, print it as-is with `[no changes]` noted inline.

---

### Step 7 — Preview

Display the full letter in terminal:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
COVER LETTER PREVIEW — [company] | [job_title]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[name]
[address]
[email]

[company_name]
[company_address]

[date]

Dear Hiring Manager,

[INTRO text]

[PARA1 text]

[PARA2 text]

[PARA3 text]

[CONCLUSION text]

Yours Faithfully,
[name]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[A]pprove  |  [F]eedback: describe changes
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

### Step 8 — Approval loop

**If user types `A`** — proceed to Step 9.

**If user gives feedback** (e.g. "Make para2 focus more on the collaboration aspect;
remove the mention of CI/CD"):
- Re-run the Cover Letter Writer sub-agent (Step 5) with the original prompt PLUS:
  ```
  REFINEMENT FEEDBACK (apply to the next draft):
  [user feedback verbatim]

  Previous draft:
  [INTRO] ...
  [PARA1] ...
  [PARA2] ...
  [PARA3] ...
  [CONCLUSION] ...
  ```
- Apply humanisation pass (Step 6) to the new draft
- Re-display preview (Step 7)
- **Maximum 3 refinement cycles.** After the 3rd feedback cycle, proceed regardless
  with the latest draft and inform the user:
  `"Maximum refinement cycles reached — proceeding with the current draft."`

---

### Step 9 — Render DOCX → PDF → DB

**9a. Build the JSON payload**

Construct:
```json
{
    "name":           "[from .cv-profile.json]",
    "address_line1":  "[from .cv-profile.json]",
    "address_line2":  "[from .cv-profile.json]",
    "address_line3":  "[from .cv-profile.json]",
    "email":          "[from .cv-profile.json]",
    "company_name":   "[company]",
    "company_address": "[company_address from Step 3, may be empty]",
    "date":           "[date formatted as e.g. 14th March 2026]",
    "salutation":     "Dear Hiring Manager,",
    "intro":          "[INTRO text]",
    "para1":          "[PARA1 text]",
    "para2":          "[PARA2 text]",
    "para3":          "[PARA3 text]",
    "conclusion":     "[CONCLUSION text]",
    "company":        "[safe slug — re.sub(r'[^\\w\\-]', '_', company)]",
    "role":           "[safe slug — first 30 chars of re.sub(r'[^\\w\\-]', '_', job_title)]"
}
```

Write to `C:\Code\CV_crawl\.cv-cover-letter-tmp.json`.

**9b. Render DOCX**

```
uv run --project "C:/Code/CV_CoverLetter_Generator_Agentic_Pipeline/job-pipeline" \
    python "C:/Code/CV_crawl/tools/render_cover_letter.py" \
    "C:/Code/CV_crawl/.cv-cover-letter-tmp.json"
```

Capture stdout as `cl_docx_path`.

**9c. Convert to PDF**

```
uv run --project "C:/Code/CV_CoverLetter_Generator_Agentic_Pipeline/job-pipeline" \
    python "C:/Code/CV_crawl/tools/docx_to_pdf.py" "<cl_docx_path>"
```

Capture the PDF path printed to stdout as `cl_pdf_path`.

**9d. Update DB**

```python
uv run --project "C:/Code/CV_CoverLetter_Generator_Agentic_Pipeline/job-pipeline" python -c "
import psycopg2, os, sys, json
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(r'C:/Code/CV_crawl') / '.env')

meta     = json.loads(open(r'C:/Code/CV_crawl/.cv-apply-meta-tmp.json', encoding='utf-8').read())
cl_docx  = sys.argv[1]
cl_pdf   = sys.argv[2]

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
" "<cl_docx_path>" "<cl_pdf_path>"
```

**9e. Print final summary**

```
✓ Cover letter generated for [company] — [job_title]
  DOCX: [cl_docx_path]
  PDF:  [cl_pdf_path]
```
