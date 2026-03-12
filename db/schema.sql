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

-- ── Habits ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS habits (
    id                  SERIAL PRIMARY KEY,
    name                TEXT NOT NULL,
    frequency           TEXT DEFAULT 'daily'
                        CHECK (frequency IN ('daily', 'weekly')),
    target_days         TEXT[],          -- ['mon','wed','fri'] for weekly habits
    streak_count        INT DEFAULT 0,
    longest_streak      INT DEFAULT 0,
    forgiveness_window  INT DEFAULT 1,   -- missed days before streak resets
    is_active           BOOLEAN DEFAULT TRUE,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

-- ── Habit logs ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS habit_logs (
    id          SERIAL PRIMARY KEY,
    habit_id    INT NOT NULL REFERENCES habits(id) ON DELETE CASCADE,
    log_date    DATE NOT NULL DEFAULT CURRENT_DATE,
    status      TEXT NOT NULL CHECK (status IN ('done', 'skipped', 'missed')),
    note        TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (habit_id, log_date)
);
CREATE INDEX idx_habit_logs_date ON habit_logs(log_date DESC);

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
    category      TEXT NOT NULL UNIQUE,
    monthly_limit NUMERIC(12, 2) NOT NULL,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

-- ── Events ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS events (
    id                SERIAL PRIMARY KEY,
    title             TEXT NOT NULL,
    description       TEXT,
    event_date        DATE NOT NULL,
    event_time        TIME,
    project_id        INT REFERENCES projects(id) ON DELETE SET NULL,
    is_recurring      BOOLEAN DEFAULT FALSE,
    recurrence        TEXT CHECK (recurrence IN ('daily','weekly','monthly','yearly', NULL)),
    remind_1day       BOOLEAN DEFAULT TRUE,
    remind_1hour      BOOLEAN DEFAULT TRUE,
    reminded_1day     BOOLEAN DEFAULT FALSE,   -- flag: 1-day reminder already sent
    reminded_1hour    BOOLEAN DEFAULT FALSE,   -- flag: 1-hour reminder already sent
    created_at        TIMESTAMPTZ DEFAULT NOW(),
    updated_at        TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_events_date ON events(event_date);
