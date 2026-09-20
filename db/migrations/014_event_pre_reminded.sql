-- 014_event_pre_reminded.sql
-- Adds pre_reminded_at to track early warning reminders (e.g. 30 minutes before)
-- while reminded_at tracks exact-time reminders.

ALTER TABLE events ADD COLUMN IF NOT EXISTS pre_reminded_at TIMESTAMPTZ;

-- Ensure feedback table exists if needed
CREATE TABLE IF NOT EXISTS feedback (
    id SERIAL PRIMARY KEY,
    intent_used TEXT,
    user_correction TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
