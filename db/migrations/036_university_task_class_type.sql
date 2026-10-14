ALTER TABLE tasks ADD COLUMN IF NOT EXISTS class_type TEXT DEFAULT 'curs';
ALTER TABLE tasks DROP CONSTRAINT IF EXISTS tasks_class_type_check;
ALTER TABLE tasks ADD CONSTRAINT tasks_class_type_check CHECK (class_type IN ('curs', 'seminar'));
