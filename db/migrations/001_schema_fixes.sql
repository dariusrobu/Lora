-- migrations/001_schema_fixes.sql
-- Run: psql $DATABASE_URL -f db/migrations/001_schema_fixes.sql
-- Description: Adds missing columns and tables for Lora v2

BEGIN;

-- 1. goals: add category column
ALTER TABLE goals ADD COLUMN IF NOT EXISTS category VARCHAR(50);

-- 2. subjects: add missing columns
ALTER TABLE subjects ADD COLUMN IF NOT EXISTS professor TEXT;
ALTER TABLE subjects ADD COLUMN IF NOT EXISTS credits INT;
ALTER TABLE subjects ADD COLUMN IF NOT EXISTS total_classes INT DEFAULT 0;
ALTER TABLE subjects ADD COLUMN IF NOT EXISTS total_seminars INT DEFAULT 0;
ALTER TABLE subjects ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;
ALTER TABLE subjects ADD COLUMN IF NOT EXISTS min_attendance_pct INT DEFAULT 70;

-- Drop old teacher column if exists (renamed to professor)
-- ALTER TABLE subjects DROP COLUMN IF EXISTS teacher;

-- 3. Create focus_sessions table if not exists
CREATE TABLE IF NOT EXISTS focus_sessions (
    id                  SERIAL PRIMARY KEY,
    session_date        DATE NOT NULL DEFAULT CURRENT_DATE,
    duration_min         INTEGER NOT NULL,
    task_description     TEXT,
    completed           BOOLEAN DEFAULT FALSE,
    interrupted_at      INTEGER,
    created_at          TIMESTAMP DEFAULT NOW()
);

-- 4. Create grades table if not exists
CREATE TABLE IF NOT EXISTS grades (
    id              SERIAL PRIMARY KEY,
    subject_id      INTEGER REFERENCES subjects(id) ON DELETE CASCADE,
    grade           NUMERIC(4,2) NOT NULL,
    grade_type      TEXT CHECK (grade_type IN ('partial', 'exam', 'laborator', 'proiect', 'colocviu')),
    notes           TEXT,
    graded_at       TIMESTAMP DEFAULT NOW(),
    created_at      TIMESTAMP DEFAULT NOW()
);

-- 5. Create attendances table (rename from attendance if exists)
-- Check if old attendance table exists
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'attendance') THEN
        -- Migrate data from attendance to attendances
        INSERT INTO attendances (schedule_id, subject_id, class_date, attended, created_at)
        SELECT schedule_id, NULL, attendance_date, (status = 'present'), created_at
        FROM attendance
        ON CONFLICT (schedule_id, class_date) DO NOTHING;

        -- Drop old table
        DROP TABLE IF EXISTS attendance CASCADE;
    END IF;
EXCEPTION WHEN undefined_table THEN
    -- Table doesn't exist, nothing to do
    NULL;
END $$;

-- 6. Create attendances table if not exists
CREATE TABLE IF NOT EXISTS attendances (
    id              SERIAL PRIMARY KEY,
    schedule_id     INTEGER REFERENCES schedule(id) ON DELETE CASCADE,
    subject_id      INTEGER REFERENCES subjects(id) ON DELETE CASCADE,
    class_date      DATE NOT NULL,
    attended        BOOLEAN NOT NULL,  -- TRUE = present, FALSE = absent
    created_at      TIMESTAMP DEFAULT NOW(),
    UNIQUE(schedule_id, class_date)
);

CREATE INDEX IF NOT EXISTS idx_attendance_date ON attendances(class_date);

-- 7. Fix exams table (add subject_name and created_at if missing)
ALTER TABLE exams ADD COLUMN IF NOT EXISTS subject_name TEXT;
ALTER TABLE exams ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT NOW();

-- Update subject_name from subjects table where NULL
UPDATE exams e
SET subject_name = s.name
FROM subjects s
WHERE e.subject_id = s.id AND e.subject_name IS NULL;

COMMIT;
