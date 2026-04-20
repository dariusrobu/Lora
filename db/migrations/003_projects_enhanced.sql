-- Projects Enhanced Migration
-- Run: psql $DATABASE_URL -f db/migrations/003_projects_enhanced.sql

-- 1. Add metadata columns to projects
ALTER TABLE projects ADD COLUMN IF NOT EXISTS deadline DATE;
ALTER TABLE projects ADD COLUMN IF NOT EXISTS priority VARCHAR(20) DEFAULT 'medium' CHECK (priority IN ('high', 'medium', 'low'));
ALTER TABLE projects ADD COLUMN IF NOT EXISTS category VARCHAR(50);
ALTER TABLE projects ADD COLUMN IF NOT EXISTS progress_pct INT DEFAULT 0 CHECK (progress_pct >= 0 AND progress_pct <= 100);

-- 2. Auto-calculate progress from linked tasks
-- This function updates project progress based on completed tasks
CREATE OR REPLACE FUNCTION update_project_progress()
RETURNS TRIGGER AS $$
BEGIN
    WITH task_stats AS (
        SELECT project_id,
               COUNT(*) FILTER (WHERE status = 'done') AS completed,
               COUNT(*) AS total
        FROM tasks
        WHERE project_id IS NOT NULL
        GROUP BY project_id
    )
    UPDATE projects p
    SET progress_pct = CASE
        WHEN ts.total = 0 THEN 0
        ELSE ROUND((ts.completed::NUMERIC / ts.total::NUMERIC) * 100)
    END
    FROM task_stats ts
    WHERE p.id = ts.project_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to auto-update progress when tasks change
DROP TRIGGER IF EXISTS tasks_progress_trigger ON tasks;
CREATE TRIGGER tasks_progress_trigger
AFTER INSERT OR UPDATE OR DELETE ON tasks
FOR EACH ROW EXECUTE FUNCTION update_project_progress();

-- 3. Add project_links table for milestones/dependencies
CREATE TABLE IF NOT EXISTS project_links (
    id SERIAL PRIMARY KEY,
    source_project_id INT REFERENCES projects(id) ON DELETE CASCADE,
    target_project_id INT REFERENCES projects(id) ON DELETE CASCADE,
    link_type VARCHAR(20) DEFAULT 'milestone' CHECK (link_type IN ('milestone', 'blocks', 'depends')),
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(source_project_id, target_project_id, link_type)
);

-- 4. Add project_notes view (notes linked to projects)
-- Already supported via notes.project_id, this just ensures the FK exists
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'notes_project_id_fkey'
    ) THEN
        ALTER TABLE notes ADD CONSTRAINT notes_project_id_fkey
        FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE SET NULL;
    END IF;
END $$;

-- 5. Update project queries to include task counts
-- (handled in queries/projects.py update)

-- 6. Seed default categories if needed
-- (optional, can be added via frontend later)