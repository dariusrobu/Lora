-- Migration: 021_project_progress_soft_delete.sql
-- Description: Fixes project progress calculation to ignore soft-deleted tasks.

CREATE OR REPLACE FUNCTION update_project_progress()
RETURNS TRIGGER AS $$
BEGIN
    WITH task_stats AS (
        SELECT project_id,
               COUNT(*) FILTER (WHERE status = 'done' AND deleted_at IS NULL) AS completed,
               COUNT(*) FILTER (WHERE deleted_at IS NULL) AS total
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

-- Recalculate progress for all projects immediately
WITH task_stats AS (
    SELECT project_id,
           COUNT(*) FILTER (WHERE status = 'done' AND deleted_at IS NULL) AS completed,
           COUNT(*) FILTER (WHERE deleted_at IS NULL) AS total
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
