-- Migration: 007_conversation_state.sql
-- Date: 2026-04-27
-- Description: Ensures conversation_state table exists (single-row state machine
--              for multi-turn flows) and adds the `extra` JSONB column if the table
--              was created by an older schema version without it.

CREATE TABLE IF NOT EXISTS conversation_state (
    id          SERIAL PRIMARY KEY,
    state_key   TEXT NOT NULL UNIQUE,   -- always 'current' (one row only)
    state_type  TEXT,                   -- 'awaiting_confirmation' | 'awaiting_edit_field' | 'awaiting_clarification' | null
    module      TEXT,                   -- which module the pending action belongs to
    action      TEXT,                   -- pending action e.g. 'delete'
    item_id     INT,                    -- id of the item being acted on
    extra       JSONB,                  -- any additional context needed to complete the action
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Guarantee the singleton row exists
INSERT INTO conversation_state (state_key)
VALUES ('current')
ON CONFLICT DO NOTHING;

-- Add `extra` column on existing installations that pre-date this migration
ALTER TABLE conversation_state
    ADD COLUMN IF NOT EXISTS extra JSONB;
