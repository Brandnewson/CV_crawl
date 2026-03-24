# /cv-setup - Interactive Profile & Facts Setup

Guides you through populating all the fact files the CV pipeline depends on.
Run this once when you first clone the repo, then again whenever you want to update
your profile, add a role, or add a new cover-letter story.

---

## Paths

| File | Purpose |
|---|---|
| `user_config.yaml` | Machine-specific paths and GitHub username |
| `data/cv-profile.json` | Your name, address, education, contact details |
| `data/cv-work-experience.json` | Verified facts per work experience role |
| `data/cv-harvest-store.json` | Technical project store (auto-populated in Step 4) |
| `data/cv-facts-promoted.json` | Reusable skill / technology facts |
| `data/experience-cache.json` | Per-job Q&A cache (auto-managed) |
| `story-bank.json` | Cover letter stories with facts |

---

## ORCHESTRATOR â€” run this sequence

### Step -1 â€” Detect repo root

Run:
```
git -C "<current working directory>" rev-parse --show-toplevel
```

Store the output as `REPO_ROOT`. Use `{REPO_ROOT}` for all paths below.

---

### Step 0 â€” File inventory scan

Check which files exist and which sections are complete:

```
Read and check:
  {REPO_ROOT}/user_config.yaml        â€” exists? github_username field non-empty?
  data/cv-profile.json           â€” schema_version field exists AND education array is non-empty?
  data/cv-work-experience.json   â€” exists AND work_experience array is non-empty?
  data/cv-harvest-store.json     â€” exists AND projects array is non-empty?
  data/cv-facts-promoted.json    â€” exists?
  data/experience-cache.json     â€” exists? count non-null entries with a job_id field
  story-bank.json at {REPO_ROOT}/.claude/skills/cover-letter-generation/story-bank.json
```

Display a status table:

```
Checking your profile files...

  [x] user_config.yaml         â€” exists  (github: <github_username>)    COMPLETE / MISSING
  [x] data/cv-profile.json         â€” exists  (name: <name>)                 COMPLETE / INCOMPLETE
  [x] data/cv-work-experience.json â€” exists  (<N> roles)                    COMPLETE / MISSING
  [x] data/cv-harvest-store.json   â€” exists  (<N> projects)                 COMPLETE / MISSING
  [x] data/cv-facts-promoted.json  â€” exists                                 COMPLETE / MISSING
  [~] data/experience-cache.json   â€” exists  (<N> answered entries, <M> job_ids)
  [x] story-bank.json          â€” exists  (<N> stories)

What would you like to do?
  [1] First-time setup (fill all missing sections in order)
  [2] Update user config (paths, GitHub username)
  [3] Update personal profile only
  [4] Add or edit a work experience role
  [5] Add cover letter story
  [6] Review experience cache (promote reusable facts, prune old entries)
  [Q] Quit
```

Execute whichever section the user requests. Sections are independent and can be run
in any order. If the user selects [1], run sections 0b â†’ 1 â†’ 2 â†’ 3 â†’ 4 â†’ 5 â†’ summary.

---

### Step 0b â€” User config (user_config.yaml)

**Target file:** `{REPO_ROOT}/user_config.yaml`

Load the file if it exists. For each field, show the current value in brackets and let
the user press Enter to keep it or type a new value:

```
--- USER CONFIGURATION ---
GitHub username [<current or blank>]:
CV output directory (where DOCXs are saved) [<current or repo_root/cv-outputs>]:
Job hunting docs folder (optional, for /cv-harvest) [<current or blank>]:
Application tracker path (optional) [<current or cv_output_dir/applications_tracker.xlsx>]:
```

Write / update `user_config.yaml` with the four fields:
```yaml
github_username: "<value>"
cv_output_dir: "<value>"
job_hunting_dir: "<value>"
applications_tracker_path: "<value>"
```

Print: `Saved user_config.yaml`

---

### Step 1 â€” Personal profile

**Target file:** `{REPO_ROOT}/data/cv-profile.json`

Load the file if it exists. For each field, show the current value in brackets and let
the user press Enter to keep it or type a new value.

```
--- PERSONAL PROFILE ---
```

Prompt for each field:
- `Name [<current>]:` â€” maps to `"name"`
- `Email [<current>]:` â€” maps to `"email"`
- `Address line 1 [<current>]:` â€” maps to `"address_line1"`
- `Address line 2 [<current>]:` â€” maps to `"address_line2"`
- `Address line 3 [<current>]:` â€” maps to `"address_line3"`
- `GitHub (e.g. github.com/username) [<current or blank>]:` â€” maps to `"github"`
- `LinkedIn URL [<current or blank>]:` â€” maps to `"linkedin"`

```
--- EDUCATION ---
How many university degrees / qualifications? [<count of existing>]:
```

For each education entry (add new one if count increases):
- `Institution name [<current>]:`
- `Degree / qualification [<current>]:`
- `Year of graduation (or expected) [<current>]:`
- `Grade or classification (e.g. First Class predicted) [<current>]:`
- `Notable modules â€” comma-separated, press Enter to skip [<current>]:`

```
--- PRIOR QUALIFICATIONS ---
Any additional qualifications? [Y/n]:
```

For each prior qualification:
- `Institution [<current>]:`
- `Qualification title [<current>]:`
- `Year completed [<current>]:`

Write the completed v2 schema to `data/cv-profile.json`:

```json
{
  "schema_version": 2,
  "name": "...",
  "address_line1": "...",
  "address_line2": "...",
  "address_line3": "...",
  "email": "...",
  "education": [
    {
      "institution": "...",
      "degree": "...",
      "graduation_year": ...,
      "grade": "...",
      "notable_modules": ["..."]
    }
  ],
  "prior_education": [
    {
      "institution": "...",
      "qualification": "...",
      "year": ...
    }
  ],
  "github": "...",
  "linkedin": "..."
}
```

Print: `Saved data/cv-profile.json`

---

### Step 2 â€” Work experience roles

**Target file:** `{REPO_ROOT}/data/cv-work-experience.json`

Load the file if it exists.

Display existing roles:
```
--- WORK EXPERIENCE ---
Existing roles:
  1. <org> â€” <role>  [<N> facts, <M> explicit_not constraints]
  2. ...

Options:
  [A] Add a new role
  [E1..EN] Edit an existing role (add / remove facts or constraints)
  [D1..DN] Delete a role entirely (asks for confirmation)
  [N] Skip / done
```

#### 2a â€” Existing CV upload (primary path)

Before prompting for individual roles, ask:

```
Do you have an existing CV to upload? Providing one means I can auto-populate
your work experience without you typing anything.
CV file path (DOCX preferred, Enter to skip):
```

**If a file path is provided:**
- If the file is a DOCX, use the `docx` skill to extract its full text content
- If the file is a PDF, extract text using:
  ```
  uv run --project "{REPO_ROOT}" python - <<'PY'
  import sys
  import pypdf
  r = pypdf.PdfReader(sys.argv[1])
  print("\n".join(p.extract_text() or "" for p in r.pages))
  PY
  ```
- Parse every work experience section: extract org name, role title, dates, and all
  bullet points verbatim
- For each role found, generate a `verified_facts[]` list from the bullets
  (split compound bullets, normalise tense to past)
- Display extracted roles for quick review:
  ```
  Extracted from CV:
    1. <Org Name> â€” <Role Title> (<Start> â€“ <End>)
       1. <fact text>
       2. <fact text>
       ...  (<N> facts)
    2. ...

  Look right? [Y to accept all / enter role numbers to edit / A to edit all]:
  ```
- After acceptance, ask: **"Anything we missed that might be useful to add?"**
  User types any extra facts free-form (one per line, blank line to finish).
  Append these to the relevant role's `verified_facts[]`.
- For technical roles, offer repo analysis as a supplement:
  ```
  Want me to scan a code repo to find additional technical facts for <org>? [y/N]:
  ```
  If yes, ask for the repo path and scan it (list files, read README, detect tech stack).

**If no CV is provided (or user skips):**
Fall through to the manual role-by-role flow below.

#### Manual role entry

**Adding a new role:**

```
Organisation name:
Job title / role:
Start date (e.g. Sep 2023) [optional]:
End date or "Present" [optional]:
Is this a technical / software engineering role? [Y/n]:
```

Then:
```
Tell me about this role. Describe what you did, built, or achieved â€” one fact per line.
Type a blank line when you're done. Be specific: tools, outcomes, scale.

Fact 1:
Fact 2:
...
```

Parse each line as a separate entry in `verified_facts[]`. Do not paraphrase or combine â€”
store the user's exact words.

```
Are there things this role should NEVER claim you did (e.g. "No C++ work")?
Constraint 1 (press Enter to skip):
Constraint 2:
...
```

Store constraints in `explicit_not[]`.

Append the new role object to `work_experience[]` and write the file.

**Editing an existing role:**

Display the role's `verified_facts` numbered list:
```
<org> â€” <role>
Facts:
  1. <fact text>
  2. <fact text>
  ...
Constraints (explicit_not):
  1. <constraint>
  ...

[A] Add a new fact
[D1..DN] Delete a fact by number
[C] Add a constraint
[DC1..DCN] Delete a constraint by number
[X] Done editing this role
```

Apply changes and write the file.

Print: `Saved data/cv-work-experience.json  (<N> roles, <total facts> facts)`

---

### Step 3 â€” Cover letter stories

**Target file:** `{REPO_ROOT}/.claude/skills/cover-letter-generation/story-bank.json`

Load the file.

Display existing stories:
```
--- COVER LETTER STORIES ---
Existing stories:
  1. <label>  â€”  <title>  [<N> facts]
  2. ...

Options:
  [A] Add a new story
  [E1..EN] Edit an existing story
  [D1..DN] Delete a story (asks for confirmation)
  [N] Skip / done
```

**Adding a new story:**

```
Story label (short snake_case, e.g. jaguar_alkamel):
Story title (human-readable, e.g. "Jaguar Alkamel Timing Feed Converter"):
Themes â€” comma-separated descriptive themes (e.g. "ownership, tool-building, stakeholder"):
Keyword heuristics â€” JD keywords that would make this story relevant (comma-separated):

Now add the facts for this story. One sentence per line. Press Enter on a blank line when done.
Only include facts you know to be true â€” no embellishment.

Fact 1:
Fact 2:
...

Things to NEVER say about this story (press Enter to skip):
Do not say 1:
Do not say 2:
...
```

Build and add the story object. Omit `work_experience_ref` (leave null) â€” it can be
added manually later.

**Editing an existing story:**

Display numbered facts list and do_not_say list. Offer add/delete for each.

Write the updated file.

Print: `Saved story-bank.json  (<N> stories)`

---

### Step 4 â€” Technical projects harvest

Work experience comes from Step 2. Technical projects come from two independent sources.

#### Source A â€” CV technical projects section

If the uploaded CV (Step 2) contained a technical projects section, those projects were
already extracted. Show them for quick review:

```
Projects found in CV:
  1. <Project Name>  (<N> bullets)
  2. ...
These will be included in your project store. Edit? [Y/n]:
```

If the user wants to edit a project, show its bullets numbered and offer add/delete.

#### Source B â€” GitHub public repos (supplemental)

Read `GITHUB_USERNAME` from `user_config.yaml`. If blank, skip this source and note it.

```
Fetching public repos for github.com/{GITHUB_USERNAME}...
```

- Call `https://api.github.com/users/{GITHUB_USERNAME}/repos?sort=updated&per_page=30`
- For each repo updated in the last 24 months: read description, topics, README (first 500 chars),
  latest commit messages
- Generate 2â€“3 project bullet candidates per repo
- Present them for inclusion/exclusion:
  ```
  GitHub repos found (not already in CV):
    [x] <repo_name>  â€” <language>, <topics>
    [x] <repo_name>  â€” <language>, <topics>
    [ ] dotfiles     â€” (low signal, skipped)
  Include/exclude? [Enter to accept checked, type numbers to toggle]:
  ```
- Accepted repos are merged into the project store with generated bullets

#### Merge and write

Combine CV projects + accepted GitHub repos â†’ write `{REPO_ROOT}/data/cv-harvest-store.json`:

```json
{
  "generated_at": "<ISO timestamp>",
  "projects": [
    {
      "name": "<project_name>",
      "title": "<short human title>",
      "description": "<one sentence>",
      "tech_tags": ["..."],
      "standout_factor": "...",
      "bullets": [
        {
          "text": "...",
          "confidence": "high|medium|low",
          "keywords_matched": ["..."],
          "scale_metrics_known": true|false,
          "gap_question": null,
          "question_id": "..."
        }
      ]
    }
  ]
}
```

Print:
```
Project store written:
  From CV:     <N> projects
  From GitHub: <M> projects
  Total:       <N+M> projects, <X> bullets â†’ data/cv-harvest-store.json
```

If both sources were skipped/empty, print a note that `/cv-harvest` can populate this
file automatically from a deeper repo + GitHub scan.

---

### Step 5 â€” Promote facts from experience cache (optional)

**Target files:**
- `{REPO_ROOT}/data/experience-cache.json` (read + prune)
- `{REPO_ROOT}/data/cv-facts-promoted.json` (write promotions)

Load `data/experience-cache.json`. Skip this step entirely if there are no entries with a
non-null `answer` and a `ts` (timestamp) field.

```
--- EXPERIENCE CACHE REVIEW ---
Your cache has <N> answered entries across <M> job_ids (<list job_ids>).
Some answers may be worth keeping as permanent facts rather than job-specific data.

Reviewing answered entries...
```

For each entry where `answer` is not null and `answer` is not empty:

```
Key:    <entry_key>
Answer: "<answer text>"
Job:    <job_id>  |  Date: <ts>

  [K] Keep as job-specific (leave in cache)
  [P] Promote to permanent facts (move to data/cv-facts-promoted.json)
  [D] Delete (remove from cache entirely)
  [S] Skip rest of entries
```

When the user selects [P], ask:
```
Category? [skills / technology_answers / deployment_answers / other]:
Key name for this fact (e.g. "cpp", "node_js", "production_deployment"):
```

Add to `data/cv-facts-promoted.json` under the chosen category:
```json
{
  "answer": "<answer text>",
  "promoted_from_job": <job_id>
}
```

When done reviewing, remove all [D]-marked entries and any [P]-marked entries from
`data/experience-cache.json`. Write both files.

Update `_meta.archived_jobs` in `data/experience-cache.json` with any job_ids that were
fully reviewed (all their entries resolved).

Print:
```
Promoted <N> facts to data/cv-facts-promoted.json
Removed  <M> entries from data/experience-cache.json
```

---

### Step 6 â€” Summary

Print:

```
--- SETUP COMPLETE ---
  user_config.yaml           âœ“  github: <username>, output: <cv_output_dir>
  data/cv-profile.json           âœ“  <name>
  data/cv-work-experience.json   âœ“  <N> roles, <total> facts
  data/cv-harvest-store.json     âœ“  <N> projects, <X> bullets
  story-bank.json            âœ“  <N> stories

You are ready to run:
  /cv-discover  â€” search for and score new jobs
  /cv-apply     â€” generate a tailored CV for any job in your DB
  /cv-harvest   â€” re-run project analysis to refresh your experience store
```

