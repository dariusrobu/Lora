CREATE TABLE apple_event_links (
    owner_id BIGINT NOT NULL,
    entity_id UUID NOT NULL,
    apple_uid TEXT NOT NULL,
    apple_revision TEXT NOT NULL,
    last_synced_version INT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (owner_id, entity_id),
    UNIQUE (owner_id, apple_uid)
);
