# /cv-discover - Job Discovery Pipeline

Searches for new jobs using JobSpy, deduplicates, scores with OpenAI, and shows
ranked results. Requires a running PostgreSQL database and `OPENAI_API_KEY` in `.env`.

---

## Paths

| Asset | Path |
|---|---|
| Config | `C:\Code\CV_crawl\discovery\config.yaml` |
| Scoring profile | `C:\Code\CV_crawl\profile\scoring_profile.yaml` |
| Automation lessons | `C:\Code\CV_crawl\LESSONS.md` |
| uv project | `C:\Code\CV_crawl\` |
| .env | `C:\Code\CV_crawl\.env` |

---

## ORCHESTRATOR - run this sequence

Before executing any shell/Python snippet, read `C:\Code\CV_crawl\LESSONS.md`
and apply relevant rules (especially L001 for shell quoting).
If a recurring automation failure appears, append a new lesson entry with
symptom, root cause, and safe pattern.

### Step 0 - Load current config

Read `C:\Code\CV_crawl\discovery\config.yaml` and display the current settings:

```
--- CURRENT SEARCH CONFIG ---
  Search terms:  forward deployed engineer, AI engineer, software engineer, ...
  Legacy location fallback: London, UK
  Explicit locations: London, Toronto, New York, San Francisco, Seattle
  Sites:         linkedin, glassdoor, indeed
  City source:   scoring_profile.locations.preferred (default)
  Results/term:  30
  Hours old:     25
  Salary floor:  GBP 40,000

What would you like to do?
  [R] Run discovery with current config
  [U] Update config then run
  [E] Edit config only (don't run)
  [Q] Quit
```

If the user selects [Q], stop immediately.

---

### Step 1 (if [U] or [E]) - Interactive config update

Present each field with its current value in brackets. The user presses Enter to keep
the current value or types a new one:

```
Search terms (comma-separated, Enter to keep):
  [forward deployed engineer, AI engineer, ...]:

Location [London, UK]:

Locations (comma-separated city list, optional):
  [London, Toronto, New York, San Francisco, Seattle]:

Sites - comma-separated from: linkedin, glassdoor, indeed
  [linkedin, glassdoor, indeed]:

Results per search term [30]:

Max hours old [25]:

Salary floor GBP [40000]:

Title exclusion keywords (comma-separated, Enter to keep current):
  [senior, staff, lead, ...]:
```

Write the updated config atomically using the script entrypoint:

```bash
uv run --project "C:/Code/CV_crawl" \
    python "C:/Code/CV_crawl/tools/update_discovery_config.py" \
    --search-terms "<comma_separated_terms>" \
    --location "<location>" \
    --locations "<comma_separated_locations>" \
    --sites "<comma_separated_sites>" \
    --results-wanted <int> \
    --hours-old <int> \
    --salary-floor <int> \
    --title-keywords "<comma_separated_keywords>" \
    --description-keywords "<comma_separated_keywords>"
```

After saving, confirm: `Config saved to discovery/config.yaml`

If the user selected [E] (edit only), stop here.

---

### Step 2 - Refresh discovery statuses (safe reopen)

```
uv run --project "C:/Code/CV_crawl" \
    python "C:/Code/CV_crawl/tools/refresh_discovery_state.py" \
    --reopen-cv-generated-days 7
```

Read and display refresh summary:
- `rejected_rows_reopened`
- `cv_generated_rows_reopened`
- `total_rows_reopened`

---

### Step 3 - Run discovery (search)

```
uv run --project "C:/Code/CV_crawl" python "C:/Code/CV_crawl/discovery/run_search.py"
```

Print live output as it runs - the script prints per-term progress. If the DB is
unavailable, fail loudly and surface the error verbatim. Do not silently continue.
Read and display:
- resolved city source and resolved city list
- timeout ladder + cooldown policy
- `COVERAGE SUMMARY`
- `COVERAGE PER SITE`
- `COVERAGE PER CITY`
Read and display the final `ENRICHMENT FALLBACK SUMMARY` line.

If `DATABASE_URL` is not set in `.env`, print:
```
ERROR: DATABASE_URL not found. Add it to C:\Code\CV_crawl\.env and retry.
  Example: DATABASE_URL=postgresql://localhost/job_pipeline
  To set up the DB from scratch: uv run --project "C:/Code/CV_crawl" python "C:/Code/CV_crawl/db/setup_db.py"
```

---

### Step 4 - Score new jobs

```
uv run --project "C:/Code/CV_crawl" python "C:/Code/CV_crawl/discovery/scorer.py" --days 1
```

Requires `OPENAI_API_KEY` in `.env`. If missing, print:
```
ERROR: OPENAI_API_KEY not found. Add it to C:\Code\CV_crawl\.env and retry.
```

Print scoring progress as it runs (the script prints per-job status).
Read and display the final `Scoring fallback summary` line with:
- `llm_used`
- `fallback_used`
- `error_types`

---

### Step 5 - Show results

Query DB for jobs scored today with fit_score >= 0.5 and status = 'new':

```
uv run --project "C:/Code/CV_crawl" python "C:/Code/CV_crawl/tools/query_jobs.py" \
    --min-score 0.5 --status new --limit 10
```

Display:

```
--- DISCOVERY RESULTS ---
Found N new jobs. Scored M. Top results (fit >= 0.50):

  0.92  Palantir - Forward Deployed Engineer           London       GBP60-80k
        AI-intensive FDE role with real customer deployments.
        Matches: Python, LLM, customer-facing, forward deployed
        https://...

  0.85  Anduril - Software Engineer, Mission Systems   London       GBP50-70k
        Defence AI startup - deploy sensing/ML products to field customers.
        Matches: Python, distributed systems, real-time
        https://...

  0.71  ...

--------------------------------------------------------------
Run /cv-apply to generate a CV for any of these jobs.
```

If no jobs were scored above 0.5, print:
```
No jobs scored >= 0.50 from today's search.
You can lower the threshold by running: tools/query_jobs.py --min-score 0.3
```
