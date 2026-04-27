-- Migration: 008_execution_log.sql
-- Date: 2026-04-27
-- Description: Creates the execution_log table for structured logging of every
--              intent routed through core/router.py. Enables monitoring of
--              success/failure patterns, slow modules, and error tracking.

CREATE TABLE IF NOT EXISTS execution_log (
    id            SERIAL PRIMARY KEY,
    intent        TEXT,                         -- e.g. 'add_task', 'finance_log'
    module        TEXT,                         -- e.g. 'tasks', 'finance'
    success       BOOLEAN NOT NULL DEFAULT TRUE,
    error_type    TEXT,                         -- NULL on success; exception class name on failure
    error_message TEXT,                         -- NULL on success; exception message on failure
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

-- Index for quick filtering by module or success flag
CREATE INDEX IF NOT EXISTS idx_execution_log_module  ON execution_log (module);
CREATE INDEX IF NOT EXISTS idx_execution_log_success ON execution_log (success);
CREATE INDEX IF NOT EXISTS idx_execution_log_created ON execution_log (created_at DESC);
