-- Migration: 018_soft_delete_tasks.sql
-- Description: Adds soft delete support for tasks.

ALTER TABLE tasks ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;

-- Update existing indexes to ignore deleted tasks where appropriate
CREATE INDEX IF NOT EXISTS idx_tasks_deleted_at ON tasks(deleted_at) WHERE deleted_at IS NULL;
