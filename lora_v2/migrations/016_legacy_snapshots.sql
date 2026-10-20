-- Complete, immutable source snapshots. These are preservation records, not
-- a claim that every legacy domain already has a v2 editor.
CREATE TABLE legacy_snapshots (
    id UUID PRIMARY KEY,
    owner_id BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    manifest JSONB NOT NULL
);
CREATE TABLE legacy_snapshot_tables (
    snapshot_id UUID NOT NULL REFERENCES legacy_snapshots(id) ON DELETE CASCADE,
    table_name TEXT NOT NULL,
    row_count INT NOT NULL,
    sha256 TEXT NOT NULL,
    rows JSONB NOT NULL,
    PRIMARY KEY (snapshot_id, table_name)
);
