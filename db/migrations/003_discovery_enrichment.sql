-- Phase 3: Discovery enrichment + duplicate-friendly ingestion
-- Run with: psql -d job_pipeline -f db/migrations/003_discovery_enrichment.sql

-- Allow duplicate job discovery for experimentation.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'jobs_company_title_date_posted_key'
          AND conrelid = 'jobs'::regclass
    ) THEN
        ALTER TABLE jobs DROP CONSTRAINT jobs_company_title_date_posted_key;
    END IF;
END $$;

-- Persist raw discovery text and enrichment so UI/pipeline can reuse without re-calling LLMs.
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS job_description_raw TEXT;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS company_description_raw TEXT;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS enrichment_keywords JSONB;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS enrichment_version TEXT;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS enriched_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_jobs_date_posted ON jobs(date_posted);
CREATE INDEX IF NOT EXISTS idx_jobs_enriched_at ON jobs(enriched_at);
