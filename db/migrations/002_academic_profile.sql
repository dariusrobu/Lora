-- db/migrations/002_academic_profile.sql
-- Academic profile fields + vacation periods
-- Run: psql $DATABASE_URL -f db/migrations/002_academic_profile.sql

-- ── Academic Profile ─────────────────────────────────────────────────
ALTER TABLE user_profile ADD COLUMN IF NOT EXISTS university_name TEXT;
ALTER TABLE user_profile ADD COLUMN IF NOT EXISTS faculty TEXT;
ALTER TABLE user_profile ADD COLUMN IF NOT EXISTS specialization TEXT;
ALTER TABLE user_profile ADD COLUMN IF NOT EXISTS study_year INT;
ALTER TABLE user_profile ADD COLUMN IF NOT EXISTS study_group TEXT;

-- ── Vacation Periods ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS vacation_periods (
    id              SERIAL PRIMARY KEY,
    name            TEXT NOT NULL,
    start_date      DATE NOT NULL,
    end_date        DATE NOT NULL,
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_vacation_dates ON vacation_periods(start_date, end_date);

-- ── Vacation Periods (UBB 2025-2026) ────────────────────────────────
-- Standard an (non-terminal): Anul 2 din 3
INSERT INTO vacation_periods (name, start_date, end_date) VALUES
    ('Vacanță de Crăciun', '2025-12-22', '2026-01-04'),
    ('Vacanță (feb)', '2026-02-09', '2026-02-15'),
    ('Vacanța de Paști', '2026-04-13', '2026-04-19'),
    ('Vacanță (iun)', '2026-06-29', '2026-07-05'),
    ('Vacanță mare', '2026-08-03', '2026-09-26')
ON CONFLICT DO NOTHING;

-- ── User Profile Update (UBB, Anul 2, Economics, Grupa 1) ───────────
UPDATE user_profile SET
    university_name = 'UBB',
    specialization = 'Economics',
    study_year = 2,
    study_group = '1'
WHERE telegram_id = (
    SELECT telegram_id FROM user_profile LIMIT 1
);
