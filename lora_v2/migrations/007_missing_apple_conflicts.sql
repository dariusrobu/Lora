CREATE UNIQUE INDEX IF NOT EXISTS apple_missing_conflict_once
ON apple_sync_conflicts(owner_id, entity_type, entity_id, local_version)
WHERE apple_revision IS NULL AND status='pending';
