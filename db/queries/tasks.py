from typing import List, Optional, Dict, Any
from datetime import date
from core.utils import with_retry


@with_retry(max_attempts=3, base_delay=1.0)
async def add_task(
    pool,
    title: str,
    notes: Optional[str] = None,
    priority: str = "medium",
    due_date: Optional[date] = None,
    project_id: Optional[int] = None,
    is_recurring: bool = False,
    recurrence: Optional[str] = None,
) -> int:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO tasks (title, notes, priority, due_date, project_id, is_recurring, recurrence)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING id
            """,
            title,
            notes,
            priority,
            due_date,
            project_id,
            is_recurring,
            recurrence,
        )
        return row["id"]


async def get_task(pool, task_id: int) -> Optional[Dict[str, Any]]:
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM tasks WHERE id = $1", task_id)
        return dict(row) if row else None


async def get_tasks_by_title(pool, title: str) -> List[Dict[str, Any]]:
    async with pool.acquire() as conn:
        # Search for case-insensitive and diacritic-insensitive partial match
        # Requires 'unaccent' extension in Postgres
        rows = await conn.fetch(
            "SELECT * FROM tasks WHERE (unaccent(title) ILIKE unaccent($1)) AND status = 'pending' AND deleted_at IS NULL",
            f"%{title}%",
        )
        return [dict(r) for r in rows]


@with_retry(max_attempts=3, base_delay=1.0)
async def update_task(pool, task_id: int, **kwargs):
    if not kwargs:
        return

    fields = []
    values = []
    for i, (key, value) in enumerate(kwargs.items(), start=2):
        fields.append(f"{key} = ${i}")
        values.append(value)

    query = f"UPDATE tasks SET {', '.join(fields)}, updated_at = NOW() WHERE id = $1"

    async with pool.acquire() as conn:
        await conn.execute(query, task_id, *values)


@with_retry(max_attempts=3, base_delay=1.0)
async def delete_task(pool, task_id: int):
    async with pool.acquire() as conn:
        await conn.execute("UPDATE tasks SET deleted_at = NOW() WHERE id = $1", task_id)


@with_retry(max_attempts=3, base_delay=1.0)
async def restore_task(pool, task_id: int):
    async with pool.acquire() as conn:
        await conn.execute("UPDATE tasks SET deleted_at = NULL WHERE id = $1", task_id)


async def list_tasks(
    pool, status: Optional[str] = "pending", project_id: Optional[int] = None
) -> List[Dict[str, Any]]:
    async with pool.acquire() as conn:
        query = """
            SELECT t.*, p.name AS project_name 
            FROM tasks t 
            LEFT JOIN projects p ON t.project_id = p.id 
            WHERE t.deleted_at IS NULL
        """
        args = []
        param_idx = 1

        if status:
            query += f" AND t.status = ${param_idx}"
            args.append(status)
            param_idx += 1

        if project_id:
            query += f" AND t.project_id = ${param_idx}"
            args.append(project_id)
            param_idx += 1

        query += """ ORDER BY p.name ASC NULLS LAST,
            CASE t.priority WHEN 'high' THEN 1 WHEN 'medium' THEN 2 WHEN 'low' THEN 3 ELSE 4 END,
            t.due_date ASC NULLS LAST"""

        rows = await conn.fetch(query, *args)
        return [dict(r) for r in rows]


@with_retry(max_attempts=3, base_delay=1.0)
async def complete_task(pool, task_id: int):
    async with pool.acquire() as conn:
        # Get task details before marking as done
        task = await conn.fetchrow("SELECT * FROM tasks WHERE id = $1", task_id)
        if not task:
            return

        await conn.execute(
            "UPDATE tasks SET status = 'done', completed_at = NOW(), updated_at = NOW() WHERE id = $1",
            task_id,
        )

        # Handle recurrence
        if task["is_recurring"] and task["recurrence"]:
            from datetime import timedelta, date
            from dateutil.relativedelta import (
                relativedelta,
            )  # Note: needs to be in requirements if used, otherwise simple logic

            new_due = task["due_date"] or date.today()
            if task["recurrence"] == "daily":
                new_due += timedelta(days=1)
            elif task["recurrence"] == "weekly":
                new_due += timedelta(weeks=1)
            elif task["recurrence"] == "monthly":
                new_due += relativedelta(months=1)

            await conn.execute(
                """
                INSERT INTO tasks (title, notes, priority, due_date, project_id, is_recurring, recurrence)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                """,
                task["title"],
                task["notes"],
                task["priority"],
                new_due,
                task["project_id"],
                True,
                task["recurrence"],
            )


async def get_completed_tasks_today(pool) -> List[Dict[str, Any]]:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT t.title, p.name AS project_name 
            FROM tasks t 
            LEFT JOIN projects p ON t.project_id = p.id 
            WHERE t.status = 'done' AND t.completed_at::date = CURRENT_DATE
            """
        )
        return [dict(r) for r in rows]


async def get_weekly_task_stats(
    pool, start_date: date, end_date: date
) -> Dict[str, Any]:
    """Returnează tasks completate per zi între start_date și end_date, plus sumele totale."""
    async with pool.acquire() as conn:
        # Get total added (needed for existing weekly review logic)
        added = await conn.fetchval(
            "SELECT COUNT(*) FROM tasks WHERE created_at::date BETWEEN $1 AND $2 AND deleted_at IS NULL",
            start_date,
            end_date,
        )

        # User's requested per-day logic
        rows = await conn.fetch(
            """
            SELECT 
                DATE(completed_at) as date,
                COUNT(*) as completed_count
            FROM tasks
            WHERE completed_at::date >= $1 
              AND completed_at::date <= $2
              AND status = 'done'
              AND deleted_at IS NULL
            GROUP BY DATE(completed_at)
            ORDER BY date
            """,
            start_date,
            end_date,
        )

        daily_stats = {row["date"]: row["completed_count"] for row in rows}

        # Return composite dict to satisfy both the user's per-day request
        # and the existing weekly review's need for 'added'/'completed' keys.
        return {
            "added": added or 0,
            "completed": sum(daily_stats.values()),
            "daily": daily_stats,  # User's requested dict
            **daily_stats,  # Also merge daily for direct key access if needed
        }


async def get_completed_tasks_per_day(
    pool, start_date: date, end_date: date
) -> List[Dict[str, Any]]:
    """Returns counts of completed tasks grouped by date."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT completed_at::date as date, COUNT(*) as count
            FROM tasks
            WHERE status = 'done' AND completed_at::date BETWEEN $1 AND $2 AND deleted_at IS NULL
            GROUP BY completed_at::date
            ORDER BY completed_at::date ASC
            """,
            start_date,
            end_date,
        )
        return [dict(r) for r in rows]


async def get_monthly_task_stats(pool, start_date, end_date) -> dict:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT 
                COUNT(*) FILTER (WHERE status = 'done' AND completed_at >= $1 AND completed_at < $2 AND deleted_at IS NULL) as completed,
                COUNT(*) FILTER (WHERE created_at >= $1 AND created_at < $2 AND deleted_at IS NULL) as created
            FROM tasks
            WHERE (created_at >= $1 AND created_at < $2) OR (completed_at >= $1 AND completed_at < $2)
        """,
            start_date,
            end_date,
        )
        return {"completed": row["completed"], "created": row["created"]}


async def find_similar_tasks(pool, title: str, user_id: int) -> List[Dict[str, Any]]:
    """
    Finds completed tasks with a similar title (fuzzy match, diacritic insensitive).
    Used to provide proactive feedback about previous performance.
    """
    # Extract keywords (words longer than 2 chars to be more inclusive)
    words = [w.strip() for w in title.split() if len(w.strip()) > 2]
    if not words:
        words = [title.strip()]

    # Use the first significant word for keyword search with unaccent
    keyword = f"%{words[0]}%"

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT title, created_at, completed_at, 
                   EXTRACT(EPOCH FROM (completed_at - created_at))/3600 as duration_hours
            FROM tasks
            WHERE status = 'done' 
              AND unaccent(title) ILIKE unaccent($1)
              AND deleted_at IS NULL
            ORDER BY completed_at DESC
            LIMIT 3
            """,
            keyword,
        )
        return [dict(r) for r in rows]
