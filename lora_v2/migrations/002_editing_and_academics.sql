ALTER TABLE expenses ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;
ALTER TABLE meals ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;
ALTER TABLE workouts ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;

CREATE TABLE IF NOT EXISTS academic_subjects (
    id UUID PRIMARY KEY,
    owner_id BIGINT NOT NULL,
    name TEXT NOT NULL,
    professor TEXT,
    credits INT,
    is_active BOOLEAN NOT NULL DEFAULT true,
    legacy_id BIGINT,
    version INT NOT NULL DEFAULT 1,
    UNIQUE (owner_id, legacy_id)
);

CREATE TABLE IF NOT EXISTS academic_schedule_rules (
    id UUID PRIMARY KEY,
    owner_id BIGINT NOT NULL,
    subject_id UUID REFERENCES academic_subjects(id) ON DELETE SET NULL,
    title TEXT NOT NULL,
    day_of_week INT NOT NULL CHECK (day_of_week BETWEEN 0 AND 6),
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    week_type TEXT NOT NULL DEFAULT 'both',
    class_type TEXT,
    room TEXT,
    valid_from DATE,
    valid_until DATE,
    is_active BOOLEAN NOT NULL DEFAULT true,
    legacy_id BIGINT,
    version INT NOT NULL DEFAULT 1,
    UNIQUE (owner_id, legacy_id)
);

CREATE TABLE IF NOT EXISTS academic_attendance (
    id UUID PRIMARY KEY,
    owner_id BIGINT NOT NULL,
    subject_id UUID REFERENCES academic_subjects(id) ON DELETE SET NULL,
    schedule_rule_id UUID REFERENCES academic_schedule_rules(id) ON DELETE SET NULL,
    class_date DATE NOT NULL,
    attended BOOLEAN NOT NULL,
    notes TEXT,
    legacy_id BIGINT,
    version INT NOT NULL DEFAULT 1,
    UNIQUE (owner_id, legacy_id)
);

CREATE TABLE IF NOT EXISTS academic_grades (
    id UUID PRIMARY KEY,
    owner_id BIGINT NOT NULL,
    subject_id UUID REFERENCES academic_subjects(id) ON DELETE SET NULL,
    label TEXT,
    value NUMERIC(5,2),
    recorded_at TIMESTAMPTZ,
    legacy_id BIGINT,
    version INT NOT NULL DEFAULT 1,
    UNIQUE (owner_id, legacy_id)
);

CREATE TABLE IF NOT EXISTS academic_exams (
    id UUID PRIMARY KEY,
    owner_id BIGINT NOT NULL,
    subject_id UUID REFERENCES academic_subjects(id) ON DELETE SET NULL,
    title TEXT NOT NULL,
    starts_at TIMESTAMPTZ NOT NULL,
    exam_type TEXT,
    room TEXT,
    notes TEXT,
    legacy_id BIGINT,
    version INT NOT NULL DEFAULT 1,
    UNIQUE (owner_id, legacy_id)
);
