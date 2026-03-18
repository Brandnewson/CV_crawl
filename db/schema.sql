-- Job Pipeline Database Schema
-- Run with: psql -d job_pipeline -f schema.sql

-- All discovered jobs, deduplicated
CREATE TABLE IF NOT EXISTS jobs (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL DEFAULT 1,
    source          TEXT NOT NULL,
    external_id     TEXT,
    company         TEXT NOT NULL,
    title           TEXT NOT NULL,
    location        TEXT,
    remote_type     TEXT,
    salary_min      INTEGER,
    salary_max      INTEGER,
    currency        TEXT DEFAULT 'GBP',
    job_url         TEXT NOT NULL,
    description     TEXT,
    job_description_raw TEXT,
    company_description_raw TEXT,
    enrichment_keywords JSONB,
    enrichment_version TEXT,
    enriched_at TIMESTAMPTZ,
    date_posted     DATE,
    date_discovered TIMESTAMPTZ DEFAULT NOW(),
    is_duplicate    BOOLEAN DEFAULT FALSE,
    duplicate_of    INTEGER REFERENCES jobs(id),
    search_term     TEXT
);

-- Your scoring + decisions per job
CREATE TABLE IF NOT EXISTS job_status (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL DEFAULT 1,
    job_id          INTEGER REFERENCES jobs(id) UNIQUE,
    fit_score       FLOAT,
    fit_summary     TEXT,
    keyword_matches JSONB,
    status          TEXT DEFAULT 'new',
    status_updated  TIMESTAMPTZ DEFAULT NOW(),
    notes           TEXT
);

-- Each generated application pack
CREATE TABLE IF NOT EXISTS application_packs (
    id                  SERIAL PRIMARY KEY,
    user_id             INTEGER NOT NULL DEFAULT 1,
    job_id              INTEGER REFERENCES jobs(id),
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    cv_path             TEXT,
    cover_letter_path   TEXT,
    job_snapshot        JSONB,
    bullets_used        JSONB,
    user_edits          TEXT,
    outcome             TEXT
);

-- CV generation sessions
CREATE TABLE IF NOT EXISTS cv_sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         INTEGER NOT NULL DEFAULT 1,
    job_id          INTEGER REFERENCES jobs(id),
    role_family     TEXT,           -- 'motorsport' | 'ai-startup' | 'forward-deployed-swe' | 'general-swe'
    seniority_level TEXT,           -- 'junior' | 'junior-mid' | 'mid' | 'senior'
    required_keywords   JSONB,
    nice_to_have_keywords JSONB,
    technical_keywords  JSONB,
    selection_plan  JSONB,          -- full CVSelectionPlan serialised
    hidden_projects JSONB,          -- list of project names to hide
    status          TEXT DEFAULT 'in_progress',  -- 'in_progress' | 'completed' | 'abandoned'
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    completed_at    TIMESTAMPTZ
);

-- CV feedback - tracks all bullet selections and approvals
CREATE TABLE IF NOT EXISTS cv_feedback (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL DEFAULT 1,
    job_id          INTEGER REFERENCES jobs(id),
    session_id      UUID REFERENCES cv_sessions(id),
    slot_section    TEXT,           -- 'work_experience' | 'technical_projects'
    slot_subsection TEXT,           -- employer or project name
    slot_index      INTEGER,
    original_text   TEXT,           -- the bullet from bank or story
    final_text      TEXT,           -- after any rephrasing
    was_approved    BOOLEAN,
    rephrase_generation INTEGER DEFAULT 0,  -- 0 = original, increments per rephrase
    source          TEXT,           -- 'master_bullets' | 'story_draft' | 'rephrasing'
    keyword_hits    JSONB,          -- keywords matched by this bullet
    relevance_score FLOAT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Search run logging
CREATE TABLE IF NOT EXISTS search_runs (
    id              SERIAL PRIMARY KEY,
    run_at          TIMESTAMPTZ DEFAULT NOW(),
    search_term     TEXT,
    source          TEXT,
    jobs_found      INTEGER,
    jobs_new        INTEGER,
    duration_secs   FLOAT
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_jobs_company ON jobs(company);
CREATE INDEX IF NOT EXISTS idx_jobs_date_discovered ON jobs(date_discovered);
CREATE INDEX IF NOT EXISTS idx_jobs_date_posted ON jobs(date_posted);
CREATE INDEX IF NOT EXISTS idx_jobs_enriched_at ON jobs(enriched_at);
CREATE INDEX IF NOT EXISTS idx_jobs_is_duplicate ON jobs(is_duplicate);
CREATE INDEX IF NOT EXISTS idx_jobs_user_id ON jobs(user_id);
CREATE INDEX IF NOT EXISTS idx_job_status_status ON job_status(status);
CREATE INDEX IF NOT EXISTS idx_job_status_fit_score ON job_status(fit_score);
CREATE INDEX IF NOT EXISTS idx_job_status_user_id ON job_status(user_id);
CREATE INDEX IF NOT EXISTS idx_application_packs_user_id ON application_packs(user_id);

-- Indexes for cv_sessions
CREATE INDEX IF NOT EXISTS idx_cv_sessions_user_id ON cv_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_cv_sessions_job_id ON cv_sessions(job_id);
CREATE INDEX IF NOT EXISTS idx_cv_sessions_status ON cv_sessions(status);

-- Indexes for cv_feedback
CREATE INDEX IF NOT EXISTS idx_cv_feedback_user_id ON cv_feedback(user_id);
CREATE INDEX IF NOT EXISTS idx_cv_feedback_job_id ON cv_feedback(job_id);
CREATE INDEX IF NOT EXISTS idx_cv_feedback_session_id ON cv_feedback(session_id);
CREATE INDEX IF NOT EXISTS idx_cv_feedback_slot ON cv_feedback(slot_section, slot_subsection);
CREATE INDEX IF NOT EXISTS idx_cv_feedback_approved ON cv_feedback(was_approved);
