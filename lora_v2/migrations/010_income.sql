CREATE TABLE IF NOT EXISTS incomes (
    id UUID PRIMARY KEY,
    owner_id BIGINT NOT NULL,
    amount NUMERIC(12,2) NOT NULL CHECK (amount > 0),
    currency TEXT NOT NULL DEFAULT 'RON',
    category TEXT,
    source TEXT,
    description TEXT,
    received_at TIMESTAMPTZ NOT NULL,
    legacy_id BIGINT,
    version INT NOT NULL DEFAULT 1,
    deleted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(owner_id,legacy_id)
);
CREATE INDEX IF NOT EXISTS income_owner_received ON incomes(owner_id,received_at DESC);
