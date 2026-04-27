-- Migration: 009_message_history.sql
-- Date: 2026-04-27
-- Description: Creates message_history table to track conversational context.

CREATE TABLE IF NOT EXISTS message_history (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_message_history_user_id ON message_history(user_id);
CREATE INDEX idx_message_history_created_at ON message_history(created_at);
