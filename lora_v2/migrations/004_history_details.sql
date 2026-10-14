ALTER TABLE calendar_entries ADD COLUMN IF NOT EXISTS all_day BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE expenses ADD COLUMN IF NOT EXISTS receipt_ref TEXT;

CREATE TABLE IF NOT EXISTS workout_exercises (
    id UUID PRIMARY KEY,
    workout_id UUID NOT NULL REFERENCES workouts(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    sets INT,
    reps INT,
    weight_kg NUMERIC(8,2),
    legacy_id BIGINT,
    UNIQUE (workout_id, legacy_id)
);
