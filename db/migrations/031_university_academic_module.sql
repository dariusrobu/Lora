-- Academic metadata needed by the University module.
ALTER TABLE grades ADD COLUMN IF NOT EXISTS weight NUMERIC(5,2);
ALTER TABLE grades ADD COLUMN IF NOT EXISTS assessment_date DATE;
ALTER TABLE grades ADD COLUMN IF NOT EXISTS assessment_title TEXT;
ALTER TABLE tasks ADD COLUMN IF NOT EXISTS university_subject_id INTEGER REFERENCES subjects(id) ON DELETE SET NULL;
ALTER TABLE projects ADD COLUMN IF NOT EXISTS university_subject_id INTEGER REFERENCES subjects(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS idx_tasks_university_subject ON tasks(university_subject_id);
CREATE INDEX IF NOT EXISTS idx_projects_university_subject ON projects(university_subject_id);
