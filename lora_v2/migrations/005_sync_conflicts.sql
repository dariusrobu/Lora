CREATE TABLE IF NOT EXISTS apple_sync_conflicts (
    id UUID PRIMARY KEY,
    owner_id BIGINT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id UUID NOT NULL,
    apple_uid TEXT NOT NULL,
    local_version INT NOT NULL,
    apple_revision TEXT,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','resolved')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (owner_id, entity_type, entity_id, local_version, apple_revision)
);
