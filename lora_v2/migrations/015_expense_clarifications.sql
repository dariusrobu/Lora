CREATE TABLE IF NOT EXISTS expense_clarifications (
    owner_id BIGINT PRIMARY KEY,
    candidate JSONB NOT NULL,
    source_capture_id UUID NOT NULL REFERENCES captures(id) ON DELETE CASCADE,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
