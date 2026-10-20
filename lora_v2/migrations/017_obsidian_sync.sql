CREATE TABLE obsidian_documents (
    owner_id BIGINT NOT NULL,
    entity_id UUID NOT NULL,
    kind TEXT NOT NULL,
    relative_path TEXT NOT NULL,
    file_fields JSONB NOT NULL,
    entity_version INT NOT NULL,
    last_synced_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    conflict TEXT,
    PRIMARY KEY(owner_id,kind,entity_id)
);
CREATE TABLE integration_status (
    name TEXT PRIMARY KEY,
    checked_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    status TEXT NOT NULL,
    detail JSONB NOT NULL DEFAULT '{}'
);
