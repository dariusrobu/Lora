ALTER TABLE attendances ADD COLUMN IF NOT EXISTS class_type TEXT;
ALTER TABLE attendances DROP CONSTRAINT IF EXISTS attendances_class_type_check;
ALTER TABLE attendances ADD CONSTRAINT attendances_class_type_check
  CHECK (class_type IS NULL OR class_type IN ('curs', 'seminar'));
