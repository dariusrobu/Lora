from typing import List, Optional, Dict, Any
from datetime import date

async def add_task(pool, title: str, notes: Optional[str] = None, priority: str = "medium", due_date: Optional[date] = None, project_id: Optional[int] = None, is_recurring: bool = False, recurrence: Optional[str] = None) -> int:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO tasks (title, notes, priority, due_date, project_id, is_recurring, recurrence)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING id
            """,
            title, notes, priority, due_date, project_id, is_recurring, recurrence
        )
        return row['id']

async def get_task(pool, task_id: int) -> Optional[Dict[str, Any]]:
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM tasks WHERE id = $1", task_id)
        return dict(row) if row else None

async def get_tasks_by_title(pool, title: str) -> List[Dict[str, Any]]:
    async with pool.acquire() as conn:
        # Search for case-insensitive partial match or exact match
        rows = await conn.fetch(
            "SELECT * FROM tasks WHERE (title ILIKE $1 OR title ILIKE $2) AND status = 'pending'",
            f"%{title}%", title
        )
        return [dict(r) for r in rows]

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

async def delete_task(pool, task_id: int):
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM tasks WHERE id = $1", task_id)

async def list_tasks(pool, status: str = "pending", project_id: Optional[int] = None) -> List[Dict[str, Any]]:
    async with pool.acquire() as conn:
        query = "SELECT * FROM tasks WHERE status = $1"
        args = [status]
        
        if project_id:
            query += " AND project_id = $2"
            args.append(project_id)
            
        query += " ORDER BY due_date ASC NULLS LAST, priority DESC"
        
        rows = await conn.fetch(query, *args)
        return [dict(r) for r in rows]

async def complete_task(pool, task_id: int):
    async with pool.acquire() as conn:
        # Get task details before marking as done
        task = await conn.fetchrow("SELECT * FROM tasks WHERE id = $1", task_id)
        if not task: return

        await conn.execute(
            "UPDATE tasks SET status = 'done', completed_at = NOW(), updated_at = NOW() WHERE id = $1",
            task_id
        )

        # Handle recurrence
        if task['is_recurring'] and task['recurrence']:
            from datetime import timedelta, date
            from dateutil.relativedelta import relativedelta # Note: needs to be in requirements if used, otherwise simple logic
            
            new_due = task['due_date'] or date.today()
            if task['recurrence'] == 'daily':
                new_due += timedelta(days=1)
            elif task['recurrence'] == 'weekly':
                new_due += timedelta(weeks=1)
            elif task['recurrence'] == 'monthly':
                new_due += relativedelta(months=1)
            
            await conn.execute(
                """
                INSERT INTO tasks (title, notes, priority, due_date, project_id, is_recurring, recurrence)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                """,
                task['title'], task['notes'], task['priority'], new_due, task['project_id'], True, task['recurrence']
            )

async def get_completed_tasks_today(pool) -> List[str]:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT title FROM tasks WHERE status = 'done' AND completed_at::date = CURRENT_DATE"
        )
        return [r['title'] for r in rows]
