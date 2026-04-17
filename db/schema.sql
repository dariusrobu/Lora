-- db/schema.sql
-- Run once: psql $DATABASE_URL -f db/schema.sql

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ── User profile ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS user_profile (
    id                    SERIAL PRIMARY KEY,
    telegram_id           BIGINT UNIQUE NOT NULL,
    name                  TEXT,
    timezone              TEXT DEFAULT 'Europe/Bucharest',
    morning_time          TEXT DEFAULT '08:00',
    eod_time              TEXT DEFAULT '21:00',
    tone                  TEXT DEFAULT 'warm',   -- warm | direct | brief
    personal_notes        TEXT,                  -- freeform facts Lora knows
    onboarding_complete   BOOLEAN DEFAULT FALSE,
    last_briefing_date    DATE,                  -- prevents duplicate daily briefing
    last_eod_date         DATE,                  -- prevents duplicate EOD message
    last_weekly_date      DATE,                  -- prevents duplicate weekly review
    last_journal_date DATE,                  -- prevents duplicate journal night prompt
    last_plan_date DATE,                  -- prevents duplicate daily plan prompt
    last_weekly_review_date DATE,                -- prevents duplicate weekly review
    last_finance_summary_date DATE,              -- prevents duplicate weekly finance summary
    last_evening_date     DATE,                  -- prevents duplicate evening flow
    created_at            TIMESTAMPTZ DEFAULT NOW(),
    updated_at            TIMESTAMPTZ DEFAULT NOW()
);

-- ── Conversation history ──────────────────────────────────────
CREATE TABLE IF NOT EXISTS conversations (
    id          SERIAL PRIMARY KEY,
    role        TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content     TEXT NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_conversations_created ON conversations(created_at DESC);

-- ── Conversation state ────────────────────────────────────────
-- Stores ephemeral state between turns (confirmations, edit flows)
CREATE TABLE IF NOT EXISTS conversation_state (
    id          SERIAL PRIMARY KEY,
    state_key   TEXT NOT NULL UNIQUE,   -- always 'current' (one row only)
    state_type  TEXT,                   -- 'awaiting_confirmation' | 'awaiting_edit_field' | null
    module      TEXT,                   -- which module the pending action belongs to
    action      TEXT,                   -- pending action e.g. 'delete'
    item_id     INT,                    -- id of the item being acted on
    extra       JSONB,                  -- any additional context needed to complete the action
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
INSERT INTO conversation_state (state_key) VALUES ('current') ON CONFLICT DO NOTHING;

-- ── Projects ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS projects (
    id          SERIAL PRIMARY KEY,
    name        TEXT NOT NULL,
    description TEXT,
    status      TEXT DEFAULT 'active'
                CHECK (status IN ('active', 'paused', 'done', 'archived')),
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ── Habits ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS habits (
    id              SERIAL PRIMARY KEY,
    name            TEXT NOT NULL,
    description     TEXT,
    frequency       TEXT DEFAULT 'daily'
                    CHECK (frequency IN ('daily', 'weekly')),
    target_days     INT[] DEFAULT ARRAY[0,1,2,3,4,5,6],  -- 0=Monday
    streak_count    INT DEFAULT 0,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    is_active       BOOLEAN DEFAULT TRUE
);
CREATE INDEX IF NOT EXISTS idx_habits_active ON habits(is_active);

CREATE TABLE IF NOT EXISTS habit_logs (
    id          SERIAL PRIMARY KEY,
    habit_id    INTEGER REFERENCES habits(id) ON DELETE CASCADE,
    log_date    DATE NOT NULL DEFAULT CURRENT_DATE,
    status      TEXT DEFAULT 'done'
                CHECK (status IN ('done', 'skipped', 'missed')),
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(habit_id, log_date)
);
CREATE INDEX IF NOT EXISTS idx_habit_logs_date ON habit_logs(log_date DESC);

-- ── Tasks ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tasks (
    id            SERIAL PRIMARY KEY,
    title         TEXT NOT NULL,
    notes         TEXT,
    priority      TEXT DEFAULT 'medium'
                  CHECK (priority IN ('high', 'medium', 'low')),
    status        TEXT DEFAULT 'pending'
                  CHECK (status IN ('pending', 'done', 'cancelled')),
    due_date      DATE,
    project_id    INT REFERENCES projects(id) ON DELETE SET NULL,
    is_recurring  BOOLEAN DEFAULT FALSE,
    recurrence    TEXT CHECK (recurrence IN ('daily', 'weekly', 'monthly', NULL)),
    completed_at  TIMESTAMPTZ,
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    updated_at    TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_tasks_status   ON tasks(status);
CREATE INDEX idx_tasks_due_date ON tasks(due_date);

-- ── Notes & Journal ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS notes (
    id          SERIAL PRIMARY KEY,
    content     TEXT NOT NULL,
    type        TEXT DEFAULT 'note' CHECK (type IN ('note', 'journal')),
    tags        TEXT[],
    mood        TEXT CHECK (mood IN ('great', 'good', 'okay', 'bad', 'awful', NULL)),
    is_pinned   BOOLEAN DEFAULT FALSE,
    project_id  INT REFERENCES projects(id) ON DELETE SET NULL,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_notes_type ON notes(type);
CREATE INDEX idx_notes_tags  ON notes USING GIN(tags);
CREATE INDEX idx_notes_search ON notes USING GIN(to_tsvector('english', content));

-- ── Finance ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS finances (
    id          SERIAL PRIMARY KEY,
    type        TEXT NOT NULL CHECK (type IN ('income', 'expense')),
    amount      NUMERIC(12, 2) NOT NULL,
    currency    TEXT DEFAULT 'RON',
    category    TEXT NOT NULL,
    description TEXT,
    tx_date     DATE NOT NULL DEFAULT CURRENT_DATE,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_finances_date ON finances(tx_date DESC);
CREATE INDEX idx_finances_type ON finances(type);

-- ── Budget limits ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS budget_limits (
    id            SERIAL PRIMARY KEY,
    category      TEXT NOT NULL,
    monthly_limit NUMERIC(12, 2) NOT NULL,
    alerted_80    BOOLEAN DEFAULT FALSE,
    alerted_100   BOOLEAN DEFAULT FALSE,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_budget_limits_category_lower ON budget_limits (LOWER(category));

-- ── Events ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS events (
    id                     SERIAL PRIMARY KEY,
    title                  TEXT NOT NULL,
    description            TEXT,
    event_date             DATE NOT NULL,
    event_time             TIME,
    event_type             TEXT DEFAULT 'event' CHECK (event_type IN ('event', 'reminder')),
    project_id             INT REFERENCES projects(id) ON DELETE SET NULL,
    is_recurring           BOOLEAN DEFAULT FALSE,
    recurrence             TEXT CHECK (recurrence IN ('daily','weekly','monthly','yearly', NULL)),
    remind_before_minutes  INT DEFAULT 30,
    reminded_at            TIMESTAMPTZ,
    remind_1day            BOOLEAN DEFAULT FALSE,
    created_at             TIMESTAMPTZ DEFAULT NOW(),
    updated_at             TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_events_date ON events(event_date);
CREATE INDEX idx_events_type ON events(event_type);

-- Migration: Ensure event_type is not null for existing rows
UPDATE events SET event_type = 'event' WHERE event_type IS NULL;
ALTER TABLE events ALTER COLUMN event_type SET NOT NULL;

-- ── Event Day Reminders (separate table for 1-day reminders) ───
CREATE TABLE IF NOT EXISTS event_day_reminders (
    event_id    INT REFERENCES events(id) ON DELETE CASCADE,
    event_date  DATE,
    sent        BOOLEAN DEFAULT FALSE,
    PRIMARY KEY (event_id, event_date)
);
CREATE INDEX idx_event_day_reminders ON event_day_reminders(event_date, sent);
-- ── Shopping List ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS shopping_list (
    id          SERIAL PRIMARY KEY,
    item        TEXT NOT NULL,
    category    TEXT,
    is_bought   BOOLEAN DEFAULT FALSE,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_shopping_bought ON shopping_list(is_bought);

-- ── Journal Entries ───────────────────────────────────────────
-- One entry per day; upserted via ON CONFLICT (entry_date)
CREATE TABLE IF NOT EXISTS journal_entries (
    id               SERIAL PRIMARY KEY,
    entry_date       DATE NOT NULL UNIQUE,
    reflection_text  TEXT,
    mood             VARCHAR(20) CHECK (mood IN ('great','good','neutral','bad','terrible', NULL)),
    tomorrow_focus   TEXT,
    created_at       TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_journal_date ON journal_entries(entry_date DESC);

-- ── Day Plans ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS day_plans (
    id               SERIAL PRIMARY KEY,
    plan_date        DATE NOT NULL UNIQUE,
    user_input       TEXT,          -- what the user said
    itinerary        TEXT NOT NULL,  -- generated itinerary
    created_at       TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_day_plans_date ON day_plans(plan_date DESC);

-- ── Goals & Goal Tasks ──────────────────────────────────────
CREATE TABLE IF NOT EXISTS goals (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    category VARCHAR(50),  -- Academice, Sport, Skills, Financiare, Lectură, Personal, Sănătate
    deadline DATE,
    progress INT DEFAULT 0 CHECK (progress >= 0 AND progress <= 100),
    status VARCHAR(20) DEFAULT 'active',  -- active, completed, paused, abandoned
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS goal_tasks (
    id SERIAL PRIMARY KEY,
    goal_id INT REFERENCES goals(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    is_completed BOOLEAN DEFAULT FALSE,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);
-- ── Health Monitoring ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS health_logs (
    id             SERIAL PRIMARY KEY,
    log_date       DATE NOT NULL UNIQUE DEFAULT CURRENT_DATE,
    sleep_hours    NUMERIC(4, 2),
    sleep_quality  TEXT CHECK (sleep_quality IN ('great', 'good', 'neutral', 'bad', 'terrible')),
    water_ml       INT,
    nutrition      TEXT CHECK (nutrition IN ('great', 'good', 'neutral', 'bad', 'terrible')),
    weight_kg      NUMERIC(5, 2),
    notes          TEXT,
    created_at     TIMESTAMPTZ DEFAULT NOW(),
    updated_at     TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_health_date ON health_logs(log_date DESC);

-- ── Insights Log ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS insight_log (
    id SERIAL PRIMARY KEY,
    insight_type TEXT NOT NULL,
    sent_at TIMESTAMP DEFAULT NOW()
);

-- ── Workouts & Sports ─────────────────────────────────────────

CREATE TABLE IF NOT EXISTS sport_types (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    category VARCHAR(50) NOT NULL, -- Forță / Cardio / Sport / Mobilitate
    has_distance BOOLEAN DEFAULT FALSE,
    has_weight BOOLEAN DEFAULT FALSE,
    has_reps BOOLEAN DEFAULT FALSE,
    icon TEXT DEFAULT '🏋️',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS exercises (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    category VARCHAR(50), -- Forță / Cardio / Mobilitate
    muscle_group TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- In case workouts and workout_exercises don't exist yet, ensure they do:
CREATE TABLE IF NOT EXISTS workouts (
    id SERIAL PRIMARY KEY,
    workout_date DATE NOT NULL,
    duration_min INT,
    calories INT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS workout_exercises (
    id SERIAL PRIMARY KEY,
    workout_id INT REFERENCES workouts(id) ON DELETE CASCADE,
    name TEXT,
    sets INT,
    reps INT,
    weight_kg NUMERIC(6, 2),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Migration for existing workouts table:
ALTER TABLE workouts DROP COLUMN IF EXISTS type;
DO $$ 
BEGIN 
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='workouts' AND column_name='sport_id') THEN 
        ALTER TABLE workouts ADD COLUMN sport_id INTEGER REFERENCES sport_types(id);
    END IF;
END $$;

-- Seed sporturi default
INSERT INTO sport_types (name, category, has_distance, has_weight, has_reps, icon) VALUES
('Gym', 'Forță', FALSE, TRUE, TRUE, '🏋️'),
('Calisthenics', 'Forță', FALSE, FALSE, TRUE, '💪'),
('Powerlifting', 'Forță', FALSE, TRUE, TRUE, '🔱'),
('Alergare', 'Cardio', TRUE, FALSE, FALSE, '🏃'),
('Ciclism', 'Cardio', TRUE, FALSE, FALSE, '🚴'),
('HIIT', 'Cardio', FALSE, FALSE, FALSE, '⚡'),
('Sărituri coarda', 'Cardio', FALSE, FALSE, FALSE, '🪢'),
('Fotbal', 'Sport', FALSE, FALSE, FALSE, '⚽'),
('Baschet', 'Sport', FALSE, FALSE, FALSE, '🏀'),
('Tenis', 'Sport', FALSE, FALSE, FALSE, '🎾'),
('Padel', 'Sport', FALSE, FALSE, FALSE, '🏓'),
('Stretching', 'Mobilitate', FALSE, FALSE, FALSE, '🧘'),
('Yoga', 'Mobilitate', FALSE, FALSE, FALSE, '🌿'),
('Recuperare activă', 'Mobilitate', FALSE, FALSE, FALSE, '♻️')
ON CONFLICT (name) DO NOTHING;

-- ── Skill Tracking ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS skills (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    category VARCHAR(50),
    unit VARCHAR(20) DEFAULT 'unit',  -- e.g. elo, min, reps, avg
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS skill_logs (
    id SERIAL PRIMARY KEY,
    skill_id INTEGER REFERENCES skills(id) ON DELETE CASCADE,
    value NUMERIC NOT NULL,
    metric TEXT,  -- optional override or detail (e.g. "blitz" for elo)
    log_date DATE DEFAULT CURRENT_DATE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_skill_logs_date ON skill_logs(log_date DESC);

-- ── Nutrition Tracking ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS meals (
    id              SERIAL PRIMARY KEY,
    meal_date       DATE NOT NULL DEFAULT CURRENT_DATE,
    meal_type       TEXT NOT NULL CHECK (meal_type IN ('mic_dejun', 'pranz', 'cina', 'gustare', 'masa')),
    total_calories  NUMERIC(8, 2) DEFAULT 0.0,
    total_protein   NUMERIC(8, 2) DEFAULT 0.0,
    total_carbs     NUMERIC(8, 2) DEFAULT 0.0,
    total_fat       NUMERIC(8, 2) DEFAULT 0.0,
    description     TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_meals_date ON meals(meal_date);

CREATE TABLE IF NOT EXISTS meal_items (
    id              SERIAL PRIMARY KEY,
    meal_id         INT NOT NULL REFERENCES meals(id) ON DELETE CASCADE,
    food_name       TEXT NOT NULL,
    quantity_g      NUMERIC(8, 2),
    calories        NUMERIC(8, 2),
    protein         NUMERIC(8, 2),
    carbs           NUMERIC(8, 2),
    fat             NUMERIC(8, 2),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS nutrition_targets (
    id              SERIAL PRIMARY KEY,
    calories        INT DEFAULT 2000,
    protein_g       INT DEFAULT 150,
    carbs_g         INT DEFAULT 200,
    fat_g           INT DEFAULT 70,
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);
INSERT INTO nutrition_targets (id, calories, protein_g, carbs_g, fat_g) 
VALUES (1, 2000, 150, 200, 70) 
ON CONFLICT (id) DO NOTHING;

-- ── Health Settings ─────────────────────────────────────────────────
-- Water target per day (ml)
ALTER TABLE user_profile ADD COLUMN IF NOT EXISTS water_target_ml INT DEFAULT 2500;

-- ── Semester Configuration ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS semester_config (
    id SERIAL PRIMARY KEY,
    semester_start DATE NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);
-- Default seed if empty
INSERT INTO semester_config (semester_start) VALUES ('2026-02-23') ON CONFLICT DO NOTHING;

-- ── University Schedule ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS subjects (
    id              SERIAL PRIMARY KEY,
    name            TEXT NOT NULL,
    professor       TEXT,
    credits         INT,
    total_classes   INT DEFAULT 0,
    total_seminars  INT DEFAULT 0,
    is_active       BOOLEAN DEFAULT TRUE,
    min_attendance_pct INT DEFAULT 70,
    avg_grade       NUMERIC(4, 2),
    target_grade    NUMERIC(4, 2),
    created_at      TIMESTAMP DEFAULT NOW()
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_subjects_name ON subjects (name);

CREATE TABLE IF NOT EXISTS schedule (
    id              SERIAL PRIMARY KEY,
    subject_id      INTEGER REFERENCES subjects(id) ON DELETE CASCADE,
    subject_name    TEXT NOT NULL,
    day_of_week     INT NOT NULL CHECK (day_of_week BETWEEN 0 AND 6),
    start_time      TIME NOT NULL,
    end_time        TIME NOT NULL,
    room            TEXT,
    class_type      TEXT CHECK (class_type IN ('curs', 'seminar', 'laborator', 'curs+seminars')),
    week_type       TEXT CHECK (week_type IN ('par', 'impar', 'both')),
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_schedule_day ON schedule(day_of_week);
CREATE INDEX IF NOT EXISTS idx_schedule_active ON schedule(is_active, day_of_week, week_type);

CREATE TABLE IF NOT EXISTS schedule_reminders_sent (
    schedule_id     INTEGER REFERENCES schedule(id) ON DELETE CASCADE,
    reminder_date   DATE NOT NULL,
    sent_at         TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (schedule_id, reminder_date)
);

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

CREATE TABLE IF NOT EXISTS exams (
    id              SERIAL PRIMARY KEY,
    subject_id      INTEGER REFERENCES subjects(id) ON DELETE CASCADE,
    subject_name    TEXT NOT NULL,
    exam_date       DATE NOT NULL,
    exam_type       TEXT CHECK (exam_type IN ('partial', 'final', 're-exam', 'colocviu', 'restanta')),
    room            TEXT,
    notes           TEXT,
    created_at      TIMESTAMP DEFAULT NOW()
);

-- ── Grades ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS grades (
    id              SERIAL PRIMARY KEY,
    subject_id      INTEGER REFERENCES subjects(id) ON DELETE CASCADE,
    grade           NUMERIC(4,2) NOT NULL,
    grade_type      TEXT CHECK (grade_type IN ('partial', 'exam', 'laborator', 'proiect', 'colocviu')),
    notes           TEXT,
    graded_at       TIMESTAMP DEFAULT NOW(),
    created_at      TIMESTAMP DEFAULT NOW()
);

-- ── Focus Sessions ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS focus_sessions (
    id                  SERIAL PRIMARY KEY,
    session_date        DATE NOT NULL DEFAULT CURRENT_DATE,
    duration_min         INTEGER NOT NULL,
    task_description     TEXT,
    completed           BOOLEAN DEFAULT FALSE,
    interrupted_at      INTEGER,
    created_at          TIMESTAMP DEFAULT NOW()
);

-- ── Memory Engine (Long-Term Facts) ───────────────────────────
CREATE TABLE IF NOT EXISTS memory_facts (
    id SERIAL PRIMARY KEY,
    category VARCHAR(50) NOT NULL,  -- 'preference', 'pattern', 'personal', 'achievement'
    fact TEXT NOT NULL,
    source VARCHAR(100),            -- 'user_stated', 'inferred', 'observed'
    confidence NUMERIC(3,2) DEFAULT 1.0,
    last_seen TIMESTAMP DEFAULT NOW(),
    times_referenced INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_memory_category ON memory_facts(category);
CREATE INDEX idx_memory_fact_search ON memory_facts USING GIN(to_tsvector('english', fact));
