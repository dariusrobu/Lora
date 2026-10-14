-- Apply only to LORA_V2_DATABASE_URL, never the legacy Lora database.
CREATE TABLE IF NOT EXISTS captures (
    id UUID PRIMARY KEY,
    owner_id BIGINT NOT NULL,
    channel TEXT NOT NULL,
    external_id TEXT NOT NULL,
    content_type TEXT NOT NULL DEFAULT 'text',
    raw_text TEXT NOT NULL DEFAULT '',
    attachment_ref TEXT,
    status TEXT NOT NULL DEFAULT 'captured' CHECK (status IN ('captured', 'processing', 'needs_input', 'processed', 'failed')),
    processing_started_at TIMESTAMPTZ,
    error_code TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    processed_at TIMESTAMPTZ,
    UNIQUE (owner_id, channel, external_id)
);

CREATE TABLE IF NOT EXISTS projects (
    id UUID PRIMARY KEY,
    owner_id BIGINT NOT NULL,
    name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    legacy_id BIGINT,
    version INT NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (owner_id, legacy_id)
);

CREATE TABLE IF NOT EXISTS tasks (
    id UUID PRIMARY KEY,
    owner_id BIGINT NOT NULL,
    title TEXT NOT NULL,
    notes TEXT,
    project_id UUID REFERENCES projects(id) ON DELETE SET NULL,
    due_at TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'done', 'cancelled')),
    legacy_id BIGINT,
    version INT NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (owner_id, legacy_id)
);
CREATE INDEX IF NOT EXISTS tasks_owner_due ON tasks(owner_id, status, due_at);

CREATE TABLE IF NOT EXISTS calendar_entries (
    id UUID PRIMARY KEY,
    owner_id BIGINT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('event', 'reminder', 'academic')),
    title TEXT NOT NULL,
    starts_at TIMESTAMPTZ NOT NULL,
    ends_at TIMESTAMPTZ,
    notes TEXT,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'done', 'cancelled')),
    followup_at TIMESTAMPTZ,
    legacy_source TEXT,
    legacy_id BIGINT,
    version INT NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (owner_id, legacy_source, legacy_id)
);
CREATE INDEX IF NOT EXISTS calendar_owner_time ON calendar_entries(owner_id, starts_at);

CREATE TABLE IF NOT EXISTS alert_occurrences (
    id UUID PRIMARY KEY,
    owner_id BIGINT NOT NULL,
    entry_id UUID NOT NULL REFERENCES calendar_entries(id) ON DELETE CASCADE,
    alert_at TIMESTAMPTZ NOT NULL,
    purpose TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'queued', 'sent', 'failed', 'cancelled')),
    attempts INT NOT NULL DEFAULT 0,
    lease_until TIMESTAMPTZ,
    sent_at TIMESTAMPTZ,
    last_error TEXT,
    UNIQUE (entry_id, alert_at, purpose)
);
CREATE INDEX IF NOT EXISTS alerts_due ON alert_occurrences(status, alert_at);

CREATE TABLE IF NOT EXISTS expenses (
    id UUID PRIMARY KEY,
    owner_id BIGINT NOT NULL,
    amount NUMERIC(12,2) NOT NULL CHECK (amount > 0),
    currency TEXT NOT NULL DEFAULT 'RON',
    category TEXT NOT NULL,
    merchant TEXT,
    description TEXT,
    spent_at TIMESTAMPTZ NOT NULL,
    meal_id UUID,
    legacy_id BIGINT,
    version INT NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (owner_id, legacy_id)
);
CREATE INDEX IF NOT EXISTS expenses_owner_spent ON expenses(owner_id, spent_at DESC);

CREATE TABLE IF NOT EXISTS expense_category_rules (
    owner_id BIGINT NOT NULL,
    merchant_key TEXT NOT NULL,
    category TEXT NOT NULL,
    source_expense_id UUID REFERENCES expenses(id) ON DELETE SET NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (owner_id, merchant_key)
);

CREATE TABLE IF NOT EXISTS meals (
    id UUID PRIMARY KEY,
    owner_id BIGINT NOT NULL,
    eaten_at TIMESTAMPTZ NOT NULL,
    description TEXT,
    estimate_source TEXT NOT NULL DEFAULT 'text',
    estimate_uncertain BOOLEAN NOT NULL DEFAULT true,
    photo_ref TEXT,
    legacy_id BIGINT,
    version INT NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (owner_id, legacy_id)
);
CREATE TABLE IF NOT EXISTS meal_items (
    id UUID PRIMARY KEY,
    meal_id UUID NOT NULL REFERENCES meals(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    grams NUMERIC(9,2),
    calories NUMERIC(9,2),
    protein_g NUMERIC(9,2),
    carbs_g NUMERIC(9,2),
    fat_g NUMERIC(9,2)
);
ALTER TABLE expenses ADD CONSTRAINT expenses_meal_fk FOREIGN KEY (meal_id) REFERENCES meals(id) ON DELETE SET NULL;

CREATE TABLE IF NOT EXISTS workouts (
    id UUID PRIMARY KEY,
    owner_id BIGINT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL,
    duration_minutes INT CHECK (duration_minutes > 0),
    activity TEXT NOT NULL,
    notes TEXT,
    legacy_id BIGINT,
    version INT NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (owner_id, legacy_id)
);

CREATE TABLE IF NOT EXISTS action_executions (
    id UUID PRIMARY KEY,
    owner_id BIGINT NOT NULL,
    idempotency_key TEXT NOT NULL,
    capture_id UUID REFERENCES captures(id) ON DELETE SET NULL,
    command_type TEXT NOT NULL,
    result JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (owner_id, idempotency_key)
);

CREATE TABLE IF NOT EXISTS proposals (
    id UUID PRIMARY KEY,
    owner_id BIGINT NOT NULL,
    source TEXT NOT NULL,
    command JSONB NOT NULL,
    reason TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'accepted', 'rejected', 'expired')),
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS proposals_source_unique ON proposals(owner_id, source);

CREATE TABLE IF NOT EXISTS notification_outbox (
    id UUID PRIMARY KEY,
    owner_id BIGINT NOT NULL,
    dedupe_key TEXT NOT NULL,
    channel TEXT NOT NULL CHECK (channel IN ('telegram', 'apple')),
    kind TEXT NOT NULL,
    payload JSONB NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'leased', 'sent', 'failed')),
    attempts INT NOT NULL DEFAULT 0,
    due_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    lease_until TIMESTAMPTZ,
    sent_at TIMESTAMPTZ,
    last_error TEXT,
    UNIQUE (owner_id, dedupe_key, channel)
);
CREATE INDEX IF NOT EXISTS notification_due ON notification_outbox(status, due_at);

CREATE TABLE IF NOT EXISTS apple_links (
    owner_id BIGINT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id UUID NOT NULL,
    apple_uid TEXT NOT NULL,
    apple_revision TEXT,
    last_synced_version INT NOT NULL,
    last_seen_at TIMESTAMPTZ,
    PRIMARY KEY (owner_id, entity_type, entity_id),
    UNIQUE (owner_id, apple_uid)
);
