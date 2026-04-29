-- db/migrations/015_contextual_nudges.sql
CREATE TABLE IF NOT EXISTS sent_nudges (
    id          SERIAL PRIMARY KEY,
    nudge_type  VARCHAR(50) NOT NULL,
    sent_at     TIMESTAMPTZ DEFAULT NOW(),
    nudge_date  DATE DEFAULT CURRENT_DATE
);

-- Unique constraint to prevent multiple nudges of same type on same day
CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_nudge_per_day ON sent_nudges(nudge_type, nudge_date);
