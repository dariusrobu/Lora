CREATE TABLE apple_event_conflicts (
    owner_id BIGINT NOT NULL,
    entity_id UUID NOT NULL,
    apple_uid TEXT NOT NULL,
    local_version INT NOT NULL,
    apple_revision TEXT,
    status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','resolved')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY(owner_id,entity_id)
);
