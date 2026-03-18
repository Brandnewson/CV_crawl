-- Phase 2: CV Generation Schema Migration
-- Run with: psql -d job_pipeline -f db/migrations/002_cv_generation.sql

-- Add user_id to jobs table (multi-user ready from day one)
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS user_id INTEGER NOT NULL DEFAULT 1;

-- Add user_id to job_status table
ALTER TABLE job_status ADD COLUMN IF NOT EXISTS user_id INTEGER NOT NULL DEFAULT 1;

-- Add user_id to application_packs table
ALTER TABLE application_packs ADD COLUMN IF NOT EXISTS user_id INTEGER NOT NULL DEFAULT 1;

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

-- Indexes for user_id on existing tables
CREATE INDEX IF NOT EXISTS idx_jobs_user_id ON jobs(user_id);
CREATE INDEX IF NOT EXISTS idx_job_status_user_id ON job_status(user_id);
CREATE INDEX IF NOT EXISTS idx_application_packs_user_id ON application_packs(user_id);
