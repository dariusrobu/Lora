-- Non-destructive synchronization journal for external projections.
CREATE TABLE IF NOT EXISTS obsidian_sync_audit (
    id BIGSERIAL PRIMARY KEY,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    source TEXT NOT NULL CHECK (source IN ('lora', 'obsidian')),
    operation TEXT NOT NULL CHECK (operation IN ('create', 'update', 'conflict', 'skip')),
    source_updated_at TIMESTAMPTZ,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_obsidian_sync_audit_entity
    ON obsidian_sync_audit(entity_type, entity_id, created_at DESC);

ALTER TABLE academic_periods
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

CREATE OR REPLACE FUNCTION touch_academic_period_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS academic_periods_updated_at ON academic_periods;
CREATE TRIGGER academic_periods_updated_at
BEFORE UPDATE ON academic_periods
FOR EACH ROW EXECUTE FUNCTION touch_academic_period_updated_at();
