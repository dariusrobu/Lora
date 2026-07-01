-- Migration: 024_lora_space_settings.sql
-- Date: 2026-06-30
-- Description: Adaugă coloane LLM în user_profile și creează tabela job_config pentru Lora Space.

ALTER TABLE user_profile ADD COLUMN IF NOT EXISTS llm_provider TEXT DEFAULT 'ollama';
ALTER TABLE user_profile ADD COLUMN IF NOT EXISTS llm_host TEXT DEFAULT 'http://localhost:11434';
ALTER TABLE user_profile ADD COLUMN IF NOT EXISTS llm_model TEXT DEFAULT 'llama3.2:3b';
ALTER TABLE user_profile ADD COLUMN IF NOT EXISTS gemini_api_key TEXT;

CREATE TABLE IF NOT EXISTS job_config (
    job_name TEXT PRIMARY KEY,
    enabled BOOLEAN DEFAULT TRUE,
    cron_time TEXT,
    last_run TIMESTAMPTZ,
    last_duration_ms INT,
    last_error TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
