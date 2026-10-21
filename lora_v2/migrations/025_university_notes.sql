CREATE TABLE IF NOT EXISTS university_notes (
    id UUID PRIMARY KEY,
    owner_id BIGINT NOT NULL,
    subject_id UUID REFERENCES academic_subjects(id) ON DELETE SET NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL DEFAULT '',
    source_path TEXT,
    version INT NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ,
    UNIQUE (owner_id, source_path)
);
CREATE INDEX IF NOT EXISTS university_notes_recent ON university_notes(owner_id, updated_at DESC)
WHERE deleted_at IS NULL;
