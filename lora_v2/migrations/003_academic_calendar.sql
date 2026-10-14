CREATE TABLE IF NOT EXISTS academic_semesters (
    owner_id BIGINT PRIMARY KEY,
    semester_start DATE NOT NULL,
    semester_end DATE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS academic_vacations (
    id UUID PRIMARY KEY,
    owner_id BIGINT NOT NULL,
    name TEXT,
    starts_on DATE NOT NULL,
    ends_on DATE NOT NULL,
    legacy_id BIGINT,
    UNIQUE (owner_id, legacy_id)
);
