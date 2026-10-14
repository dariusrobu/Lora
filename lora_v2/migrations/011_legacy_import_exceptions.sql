CREATE TABLE IF NOT EXISTS legacy_import_exceptions (
    owner_id BIGINT NOT NULL,
    source_table TEXT NOT NULL,
    legacy_id BIGINT NOT NULL,
    reason TEXT NOT NULL,
    source_data JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY(owner_id,source_table,legacy_id)
);
