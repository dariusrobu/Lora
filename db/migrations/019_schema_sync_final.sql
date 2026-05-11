-- db/migrations/019_schema_sync_final.sql
-- Description: Final schema sync for Lora stabilization.

-- 1. attendances table
ALTER TABLE attendances ADD COLUMN IF NOT EXISTS notes TEXT;

-- 2. conversation_state table
ALTER TABLE conversation_state ADD COLUMN IF NOT EXISTS last_intent JSONB;
ALTER TABLE conversation_state ADD COLUMN IF NOT EXISTS last_inserted_id INT;
ALTER TABLE conversation_state ADD COLUMN IF NOT EXISTS last_module TEXT;

-- 3. journal_entries table
ALTER TABLE journal_entries ADD COLUMN IF NOT EXISTS task_completion VARCHAR(20);
ALTER TABLE journal_entries ADD COLUMN IF NOT EXISTS skipped BOOLEAN DEFAULT FALSE;
