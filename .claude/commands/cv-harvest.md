# /cv-harvest — Personal CV Intelligence Pipeline

Orchestrates four parallel sub-agents across your Code folder, GitHub profile,
and GraduateJobHunting docs, then synthesises per-project CV entries (title,
description, bullet points) tuned to the roles you are actually applying for.

---

## Paths (hardcoded to your machine)

| Source | Path |
|---|---|
| Code projects | `C:\Code\CV_crawl` |
| Job hunting docs | `C:\Users\brans\OneDrive - University of Leeds\GraduateJobHunting` |
| GitHub username | `Brandnewson` |

---

## ORCHESTRATOR — run this sequence

### Step 0 — Discover projects list (run first, sequentially)

Run the following to get the list of top-level project folders in your Code directory.
Store this list — all later agents need it.

```powershell
Get-ChildItem "C:\Code\CV_crawl" -Directory | Select-Object -ExpandProperty Name
```

---

### Step 1 — Fire four sub-agents in PARALLEL using Task()

---

#### TASK 1 — Code Analyst

```
You are the Code Analyst sub-agent.

Your job is to inspect every project folder inside C:\Code\CV_crawl and
produce a structured profile of each one.

For EACH subdirectory (treat each as a separate project):

1. List its contents:
   Get-ChildItem "C:\Code\CV_crawl\<project>" -Recurse -Depth 2

2. Detect the tech stack by checking for:
   - package.json                              → Node/TypeScript/JavaScript
   - pyproject.toml / requirements.txt         → Python
   - Cargo.toml                                → Rust
   - go.mod                                    → Go
   - *.csproj / *.sln                          → C# / .NET
   - docker-compose.yml / Dockerfile           → containerised
   - .github/workflows/                        → CI/CD pipelines
   - folders named: agents/, pipelines/, models/, api/, infra/, workers/

3. If a README.md or README.rst exists, read its first 100 lines.

4. Count lines of code:
   (Get-ChildItem "C:\Code\CV_crawl\<project>" -Recurse -Include *.py,*.ts,*.js,*.rs,*.go,*.cs | Get-Content | Measure-Object -Line).Lines

5. Look for config files or imports that reveal these frameworks:
   - LangChain, LangGraph, CrewAI, AutoGen, Semantic Kernel (AI/agent frameworks)
   - FastAPI, Express, Django, Flask (web frameworks)
   - Celery, Redis, RabbitMQ (task queues)
   - Prisma, SQLAlchemy, Alembic (data layers)
   - Terraform, Pulumi, CDK (infra-as-code)
   - Hugging Face transformers, OpenAI SDK, Anthropic SDK

Return your findings as:

<code_intelligence>
  <project name="<folder name>">
    <path>C:\Code\CV_crawl\<folder name></path>
    <primary_language>...</primary_language>
    <frameworks>comma-separated</frameworks>
    <architecture_patterns>e.g. multi-agent, REST API, data pipeline, CLI tool</architecture_patterns>
    <scale_loc>approximate lines of code</scale_loc>
    <readme_summary>first meaningful paragraph from README, or "none"</readme_summary>
    <notable_files>list of architecturally significant files</notable_files>
  </project>
  ...one block per project folder...
</code_intelligence>
```

---

#### TASK 2 — GitHub Analyst

```
You are the GitHub Analyst sub-agent.

Fetch public activity for GitHub user: Brandnewson

1. Fetch recent repositories:
   curl -s "https://api.github.com/users/Brandnewson/repos?sort=updated&per_page=30"

   For each repo extract: name, description, language, topics, updated_at,
   stargazers_count, forks_count.

2. For repositories updated in the last 18 months, fetch the commit log:
   curl -s "https://api.github.com/repos/Brandnewson/<repo>/commits?per_page=30"

   Extract commit messages to understand what was being built/changed.

3. Identify repos that overlap with the Code folder projects by name similarity.
   Flag these as local_match="yes" — they have double evidence.

4. Fetch README content for the most active repos:
   curl -s "https://api.github.com/repos/Brandnewson/<repo>/readme" | python3 -c "
   import sys,json,base64
   d=json.load(sys.stdin)
   print(base64.b64decode(d['content']).decode()[:3000])
   "

Return findings as:

<github_intelligence>
  <repo name="..." language="..." updated="..." local_match="yes|no">
    <description>GitHub description or "none"</description>
    <topics>comma-separated</topics>
    <recent_commits>
      - commit message 1
      - commit message 2
    </recent_commits>
    <readme_excerpt>first 300 chars of README or "none"</readme_excerpt>
  </repo>
  ...
</github_intelligence>
```

---

#### TASK 3 — Job Target Analyst

```
You are the Job Target Analyst sub-agent.

Read the job applications folder to extract what roles, skills, and keywords
are being targeted — so CV bullets can be tuned to match.

Base path: C:\Users\brans\OneDrive - University of Leeds\GraduateJobHunting

1. List all subfolders (each is one job application):
   Get-ChildItem "C:\Users\brans\OneDrive - University of Leeds\GraduateJobHunting" -Directory

2. For each subfolder, find and read job description files:
   - Look for: *.txt, *.md, *job*.pdf, *JD*.pdf, *description*.pdf, *role*.pdf
   - Also read any *.docx cover letters or application notes

3. Extract text from PDFs:
   python3 -c "
   import sys
   try:
       import pypdf
       r = pypdf.PdfReader(sys.argv[1])
       print(' '.join(p.extract_text() or '' for p in r.pages[:3]))
   except ImportError:
       import subprocess
       subprocess.run(['pip','install','pypdf','--break-system-packages','-q'])
   " "path/to/file.pdf"

4. Extract text from .docx files:
   python3 -c "
   import mammoth, sys
   with open(sys.argv[1], 'rb') as f:
       print(mammoth.extract_raw_text(f).value[:3000])
   " "path/to/file.docx"
   If mammoth not installed: pip install mammoth --break-system-packages -q

5. From ALL materials, extract and rank:
   - Job titles applied for
   - Most frequently required technical skills
   - Most frequently required soft/methodological skills  
   - Company types (startup, enterprise, consultancy, research)
   - Seniority level (graduate, junior, mid)
   - Keywords appearing in 3+ job descriptions (HIGH PRIORITY for CV bullets)

Return findings as:

<job_intelligence>
  <target_roles>
    <role title="..." company="..." seniority="..."/>
    ...
  </target_roles>
  <high_priority_keywords>
    <keyword frequency="N" context="...">keyword here</keyword>
    ...sorted by frequency descending...
  </high_priority_keywords>
  <skill_clusters>
    <cluster name="e.g. AI/ML Engineering">skill1, skill2, skill3</cluster>
    <cluster name="e.g. Software Engineering">...</cluster>
  </skill_clusters>
  <company_types>list all seen</company_types>
</job_intelligence>
```

---

#### TASK 4 — Git History Analyst

```
You are the Git History Analyst sub-agent.

For each project folder in C:\Code\CV_crawl that contains a .git directory:

1. Check for git:
   Test-Path "C:\Code\CV_crawl\<project>\.git"

2. Run git log for each local repo:
   cd "C:\Code\CV_crawl\<project>"
   git log --oneline --since="18 months ago" 2>$null | Select-Object -First 60

3. Find files added over time (reveals scope of work):
   git log --all --oneline --since="18 months ago" --diff-filter=A --name-only --pretty=format: 2>$null | Sort-Object -Unique | Select-Object -First 60

4. Check for tags/releases:
   git tag --sort=-creatordate 2>$null | Select-Object -First 5

Return findings as:

<git_intelligence>
  <project name="...">
    <commit_themes>describe the arc of work — not just a list of commits</commit_themes>
    <key_milestones>any tags, major merges, architectural shifts</key_milestones>
    <velocity>approx number of commits in last 6 months</velocity>
  </project>
</git_intelligence>
```

---

### Step 2 — CV Writer sub-agent (after all four Tasks return)

Spawn the CV Writer, injecting all four intelligence blocks:

```
You are a senior technical CV writer specialising in software engineering and
AI/ML graduate roles.

You have been given intelligence from four specialist agents:

{{code_intelligence}}
{{github_intelligence}}
{{git_intelligence}}
{{job_intelligence}}

CRITICAL RULE: The <job_intelligence> block tells you exactly what keywords,
skills, and role types this person is targeting. Mirror that language precisely
wherever the evidence supports it. Never invent skills not evidenced in the code.

FOR EACH PROJECT produce a structured entry:

<project_entry name="...">

  <title>Short project title, 3–6 words, human-readable</title>

  <description>
    One sentence (max 25 words) describing what the project is and does.
    Written for a technical recruiter who may not know the domain.
  </description>

  <bullets>
    <bullet category="Agentic Systems|ML/AI|Infrastructure|Backend|Data|Tooling|Full-Stack">
      <text>
        Past-tense verb + what + how + tech stack + impact or scale.
        Mirror high-priority keywords from job_intelligence where accurate.
        If the project involves LLMs, agents, or AI pipelines — lead with that.
        Formula: [Verb] + [what was built] + [using X technology] + [achieving Y result]
      </text>
      <keywords_matched>which high_priority_keywords from job_intelligence appear here</keywords_matched>
      <confidence>high|medium|low — based on evidence quality</confidence>
    </bullet>
    <!-- 2–4 bullets per project. Prioritise the most differentiated work. -->
  </bullets>

  <tech_tags>comma-separated list of all technologies — for skills section of CV</tech_tags>

  <standout_factor>
    One sentence: what makes this project distinctive to a technical recruiter.
  </standout_factor>

</project_entry>

Wrap all entries in:
<cv_output>
  ...
</cv_output>
```

---

### Step 3 — Render and save output

Parse `<cv_output>` and print to terminal:

```
╔══════════════════════════════════════════════════════════════╗
║              CV HARVEST — github.com/Brandnewson             ║
╚══════════════════════════════════════════════════════════════╝

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 PROJECT: [Title]
 [One-sentence description]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  • [bullet 1]
  • [bullet 2]
  • [bullet 3]

  🏷  Tech: [tech_tags]
  ⭐  [standout_factor]

[...repeat for each project...]

────────────────────────────────────────────────────────────────
📋 Targeting: [list role titles from job_intelligence]
🔑 Top keywords matched: [top 5 high_priority_keywords used across bullets]
────────────────────────────────────────────────────────────────
```

Write full output (formatted bullets + raw XML) to:
`C:\Code\CV_crawl\.cv-harvest-output.md`

---

### Step 3b — Serialise experience store to JSON

After writing the output file, produce a structured JSON experience store.

Parse `<cv_output>` + the four intelligence XML blocks and write to
`C:\Code\CV_crawl\.cv-harvest-store.json`:

```python
import json, re, sys
from pathlib import Path
from datetime import datetime

# Read the output file just written
output_text = Path(r"C:\Code\CV_crawl\.cv-harvest-output.md").read_text(encoding="utf-8")

# Helper: check if any bullet has a numeric metric (%, LOC, ms, req/s, x, etc.)
def has_metric(text):
    return bool(re.search(r'\d+\s*(%|loc|ms|req|x\b|×|k\b|mb|gb|s\b)', text, re.IGNORECASE))

projects = []
# Parse each <project_entry name="...">...</project_entry> block from cv_output
for m in re.finditer(r'<project_entry name="([^"]+)">(.*?)</project_entry>', output_text, re.DOTALL):
    name = m.group(1)
    block = m.group(2)

    title_m = re.search(r'<title>(.*?)</title>', block, re.DOTALL)
    desc_m  = re.search(r'<description>(.*?)</description>', block, re.DOTALL)
    tags_m  = re.search(r'<tech_tags>(.*?)</tech_tags>', block, re.DOTALL)
    stand_m = re.search(r'<standout_factor>(.*?)</standout_factor>', block, re.DOTALL)

    bullets = []
    for bm in re.finditer(r'<bullet[^>]*>(.*?)</bullet>', block, re.DOTALL):
        bblock = bm.group(1)
        text_m  = re.search(r'<text>(.*?)</text>', bblock, re.DOTALL)
        conf_m  = re.search(r'<confidence>(.*?)</confidence>', bblock, re.DOTALL)
        kw_m    = re.search(r'<keywords_matched>(.*?)</keywords_matched>', bblock, re.DOTALL)
        btext = text_m.group(1).strip() if text_m else ""
        conf  = conf_m.group(1).strip() if conf_m else "medium"
        kws   = [k.strip() for k in kw_m.group(1).split(",")] if kw_m else []
        scale_known = has_metric(btext)
        gap_q = None
        if conf in ("medium", "low") and not scale_known:
            gap_q = f"Can you quantify the impact or scale of: \"{btext[:80]}...\"? (e.g. % improvement, number of users, lines of code, runtime reduction)"
        bullets.append({
            "text": btext,
            "confidence": conf,
            "keywords_matched": kws,
            "scale_metrics_known": scale_known,
            "gap_question": gap_q,
            "question_id": f"{name.lower().replace(' ','_')}_{len(bullets)}"
        })

    projects.append({
        "name": name,
        "title": title_m.group(1).strip() if title_m else name,
        "description": desc_m.group(1).strip() if desc_m else "",
        "tech_tags": [t.strip() for t in tags_m.group(1).split(",")] if tags_m else [],
        "standout_factor": stand_m.group(1).strip() if stand_m else "",
        "bullets": bullets
    })

store = {
    "generated_at": datetime.utcnow().isoformat() + "Z",
    "projects": projects
}

Path(r"C:\Code\CV_crawl\.cv-harvest-store.json").write_text(
    json.dumps(store, indent=2, ensure_ascii=False), encoding="utf-8"
)
print(f"Wrote .cv-harvest-store.json — {len(projects)} projects, "
      f"{sum(len(p['bullets']) for p in projects)} bullets")
```

Run this Python block inline (paste to a python3 -c call or write to a temp file and execute).
