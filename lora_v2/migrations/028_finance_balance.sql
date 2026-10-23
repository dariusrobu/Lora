-- A manually verified balance anchors the ledger without rewriting old transactions.
CREATE TABLE IF NOT EXISTS finance_balance_baselines (
    owner_id BIGINT NOT NULL,
    currency TEXT NOT NULL CHECK (currency = 'RON'),
    amount NUMERIC(14,2) NOT NULL,
    as_of TIMESTAMPTZ NOT NULL,
    version INT NOT NULL DEFAULT 1,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (owner_id, currency)
);
