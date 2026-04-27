-- Migration: 011_memory_facts_userid.sql
-- Date: 2026-04-27
-- Description: Adds user_id to memory_facts.

ALTER TABLE memory_facts ADD COLUMN IF NOT EXISTS user_id BIGINT;
-- If there are existing rows, they might need a default user_id, but usually for Lora it's a single user.
-- Update existing rows to use the default user id if needed.
-- UPDATE memory_facts SET user_id = ... WHERE user_id IS NULL;
