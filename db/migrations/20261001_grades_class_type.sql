ALTER TABLE grades ADD COLUMN IF NOT EXISTS class_type TEXT;
DO $$ BEGIN
  ALTER TABLE grades ADD CONSTRAINT grades_class_type_check CHECK (class_type IS NULL OR class_type IN ('curs', 'seminar'));
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;
