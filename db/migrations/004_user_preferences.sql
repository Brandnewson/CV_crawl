-- Migration 004: Users table + job search preferences
-- Run with: psql -d job_pipeline -f db/migrations/004_user_preferences.sql

-- Create users table (the backing row for user_id=1 used everywhere)
CREATE TABLE IF NOT EXISTS users (
    id          SERIAL PRIMARY KEY,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Seed the default user so all existing user_id=1 references have a home
INSERT INTO users (id) VALUES (1) ON CONFLICT (id) DO NOTHING;

-- Add FK constraint from jobs.user_id to users.id if not already present
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'jobs_user_id_fkey' AND conrelid = 'jobs'::regclass
    ) THEN
        ALTER TABLE jobs ADD CONSTRAINT jobs_user_id_fkey
            FOREIGN KEY (user_id) REFERENCES users(id);
    END IF;
END $$;

-- Job search preferences: one row per user, upserted on save
CREATE TABLE IF NOT EXISTS user_preferences (
    user_id                  INTEGER PRIMARY KEY REFERENCES users(id),
    search_terms             JSONB    NOT NULL DEFAULT '[]',
    role_families            JSONB    NOT NULL DEFAULT '[]',
    location                 TEXT     NOT NULL DEFAULT 'London, UK',
    country_indeed           TEXT     NOT NULL DEFAULT 'UK',
    results_wanted           INTEGER  NOT NULL DEFAULT 30,
    hours_old                INTEGER  NOT NULL DEFAULT 25,
    salary_floor             INTEGER  NOT NULL DEFAULT 40000,
    currency                 TEXT     NOT NULL DEFAULT 'GBP',
    excluded_title_keywords  JSONB    NOT NULL DEFAULT '[]',
    excluded_desc_keywords   JSONB    NOT NULL DEFAULT '[]',
    updated_at               TIMESTAMPTZ DEFAULT NOW()
);

-- Seed preferences from config.yaml defaults (populated on first GET /api/preferences if absent)
-- Actual seeding is done by the Flask endpoint falling back to config.yaml parsing.
