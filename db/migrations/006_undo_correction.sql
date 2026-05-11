-- Migration: 006_undo_correction.sql
-- Date: 2026-05-11
-- Description: Adds support for undo and correction by storing the last intent and item ID.

ALTER TABLE conversation_state ADD COLUMN IF NOT EXISTS last_intent JSONB;
ALTER TABLE conversation_state ADD COLUMN IF NOT EXISTS last_inserted_id INT;
ALTER TABLE conversation_state ADD COLUMN IF NOT EXISTS last_module TEXT;
