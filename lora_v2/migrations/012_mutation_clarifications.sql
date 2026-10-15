-- A short-lived, single outstanding clarification for conversational edits.
CREATE TABLE IF NOT EXISTS mutation_clarifications (
    owner_id BIGINT PRIMARY KEY,
    original_text TEXT NOT NULL,
    expected TEXT NOT NULL CHECK (expected IN ('target', 'last', 'category')),
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
