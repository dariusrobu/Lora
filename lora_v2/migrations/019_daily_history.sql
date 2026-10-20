CREATE TABLE expense_categories (
    id UUID PRIMARY KEY,
    owner_id BIGINT NOT NULL,
    name TEXT NOT NULL,
    icon TEXT,
    keywords TEXT[] NOT NULL DEFAULT '{}',
    is_active BOOLEAN NOT NULL DEFAULT true,
    legacy_id BIGINT,
    version INT NOT NULL DEFAULT 1,
    UNIQUE(owner_id, name),
    UNIQUE(owner_id, legacy_id)
);

CREATE TABLE personal_preferences (
    owner_id BIGINT PRIMARY KEY,
    data JSONB NOT NULL DEFAULT '{}',
    version INT NOT NULL DEFAULT 1,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE nutrition_targets_v2 (
    owner_id BIGINT PRIMARY KEY,
    calories INT,
    protein_g INT,
    carbs_g INT,
    fat_g INT,
    version INT NOT NULL DEFAULT 1,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE daily_reflections (
    id UUID PRIMARY KEY,
    owner_id BIGINT NOT NULL,
    entry_date DATE NOT NULL,
    reflection_text TEXT,
    mood TEXT,
    tomorrow_focus TEXT,
    task_completion TEXT,
    skipped BOOLEAN NOT NULL DEFAULT false,
    legacy_id BIGINT,
    version INT NOT NULL DEFAULT 1,
    deleted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(owner_id, entry_date),
    UNIQUE(owner_id, legacy_id)
);

CREATE TABLE day_plans_v2 (
    id UUID PRIMARY KEY,
    owner_id BIGINT NOT NULL,
    plan_date DATE NOT NULL,
    user_input TEXT,
    itinerary TEXT,
    wake_time TIME,
    legacy_id BIGINT,
    version INT NOT NULL DEFAULT 1,
    deleted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(owner_id, plan_date),
    UNIQUE(owner_id, legacy_id)
);
