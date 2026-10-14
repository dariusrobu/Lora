CREATE TABLE IF NOT EXISTS health_entries (
    id UUID PRIMARY KEY,
    owner_id BIGINT NOT NULL,
    log_date DATE NOT NULL,
    sleep_hours NUMERIC(4,2),
    sleep_quality TEXT CHECK (sleep_quality IN ('great','good','neutral','bad','terrible')),
    water_ml INT CHECK (water_ml >= 0),
    weight_kg NUMERIC(6,2) CHECK (weight_kg > 0),
    cigarettes INT CHECK (cigarettes >= 0),
    notes TEXT,
    legacy_id BIGINT,
    version INT NOT NULL DEFAULT 1,
    deleted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(owner_id,legacy_id)
);
CREATE UNIQUE INDEX IF NOT EXISTS health_one_active_day
ON health_entries(owner_id,log_date) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS health_owner_day ON health_entries(owner_id,log_date DESC);
