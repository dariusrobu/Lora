-- db/migrations/014_eod_interactive.sql
ALTER TABLE journal_entries ADD COLUMN IF NOT EXISTS task_completion VARCHAR(20);
ALTER TABLE journal_entries ADD COLUMN IF NOT EXISTS skipped BOOLEAN DEFAULT FALSE;
