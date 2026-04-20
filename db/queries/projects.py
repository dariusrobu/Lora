from typing import List, Optional, Dict, Any
from datetime import date


async def add_project(
    pool,
    name: str,
    description: Optional[str] = None,
    status: str = "active",
    deadline: Optional[date] = None,
    priority: str = "medium",
    category: Optional[str] = None,
) -> int:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """INSERT INTO projects (name, description, status, deadline, priority, category)
            VALUES ($1, $2, $3, $4, $5, $6) RETURNING id""",
            name,
            description,
            status,
            deadline,
            priority,
            category,
        )
        return row["id"]


async def get_project(pool, project_id: int) -> Optional[Dict[str, Any]]:
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM projects WHERE id = $1", project_id)
        return dict(row) if row else None


async def get_project_by_name(pool, name: str) -> Optional[Dict[str, Any]]:
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM projects WHERE name ILIKE $1", name)
        return dict(row) if row else None


async def list_projects(
    pool, status: Optional[str] = None, exclude_status: str = "archived"
) -> List[Dict[str, Any]]:
    async with pool.acquire() as conn:
        if status:
            rows = await conn.fetch(
                "SELECT * FROM projects WHERE status = $1 ORDER BY updated_at DESC",
                status,
            )
        else:
            rows = await conn.fetch(
                "SELECT * FROM projects WHERE status != $1 ORDER BY updated_at DESC",
                exclude_status,
            )
        return [dict(r) for r in rows]


async def get_projects_with_counts(pool) -> List[Dict[str, Any]]:
    """Get projects with task counts and overdue task counts."""
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT
                p.*,
                COUNT(t.id) FILTER (WHERE t.status = 'pending') AS pending_tasks,
                COUNT(t.id) FILTER (WHERE t.status = 'done') AS completed_tasks,
                COUNT(t.id) FILTER (WHERE t.due_date < CURRENT_DATE AND t.status = 'pending') AS overdue_tasks
            FROM projects p
            LEFT JOIN tasks t ON t.project_id = p.id
            WHERE p.status != 'archived'
            GROUP BY p.id
            ORDER BY
                p.priority DESC NULLS LAST,
                p.deadline ASC NULLS LAST,
                p.updated_at DESC
        """)
        return [dict(r) for r in rows]


async def get_project_detail(pool, project_id: int) -> Optional[Dict[str, Any]]:
    """Get full project details including tasks and notes."""
    async with pool.acquire() as conn:
        project = await conn.fetchrow(
            "SELECT * FROM projects WHERE id = $1", project_id
        )
        if not project:
            return None

        tasks = await conn.fetch(
            """
            SELECT id, title, status, priority, due_date
            FROM tasks WHERE project_id = $1
            ORDER BY
                CASE status WHEN 'pending' THEN 0 ELSE 1 END,
                due_date ASC NULLS LAST,
                priority DESC
        """,
            project_id,
        )

        notes = await conn.fetch(
            """
            SELECT id, content, type, created_at
            FROM notes WHERE project_id = $1
            ORDER BY created_at DESC
            LIMIT 5
        """,
            project_id,
        )

        return {
            **dict(project),
            "tasks": [dict(t) for t in tasks],
            "notes": [dict(n) for n in notes],
            "task_count": len(tasks),
            "pending_count": len([t for t in tasks if t["status"] == "pending"]),
        }


async def update_project_status(pool, project_id: int, status: str):
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE projects SET status = $1, updated_at = NOW() WHERE id = $2",
            status,
            project_id,
        )


async def archive_project(pool, project_id: int):
    await update_project_status(pool, project_id, "archived")


async def update_project(pool, project_id: int, **kwargs):
    if not kwargs:
        return
    valid_fields = {
        "name",
        "description",
        "status",
        "deadline",
        "priority",
        "category",
        "progress_pct",
    }
    kwargs = {k: v for k, v in kwargs.items() if k in valid_fields}
    if not kwargs:
        return
    fields = [f"{k} = ${i}" for i, k in enumerate(kwargs.keys(), start=2)]
    query = f"UPDATE projects SET {', '.join(fields)}, updated_at = NOW() WHERE id = $1"
    async with pool.acquire() as conn:
        await conn.execute(query, project_id, *kwargs.values())


async def delete_project(pool, project_id: int):
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM projects WHERE id = $1", project_id)
