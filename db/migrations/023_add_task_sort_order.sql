-- Migration: 023_add_task_sort_order.sql
-- Date: 2026-06-28
-- Description: Adds sort_order column to tasks for manual reordering

ALTER TABLE tasks ADD COLUMN IF NOT EXISTS sort_order INT DEFAULT 0;
CREATE INDEX IF NOT EXISTS idx_tasks_sort_order ON tasks(sort_order);
