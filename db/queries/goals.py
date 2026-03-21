from typing import List, Optional, Dict, Any
from datetime import date

async def create_goal(pool, title: str, description: Optional[str] = None, deadline: Optional[date] = None) -> Dict[str, Any]:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO goals (title, description, deadline)
            VALUES ($1, $2, $3)
            RETURNING *
            """,
            title, description, deadline
        )
        return dict(row)

async def list_goals(pool, status: str = 'active') -> List[Dict[str, Any]]:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM goals WHERE status = $1 ORDER BY deadline ASC NULLS LAST, created_at DESC",
            status
        )
        return [dict(r) for r in rows]

async def update_goal_progress(pool, goal_id: int, progress: int) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE goals SET progress = $1, updated_at = NOW() WHERE id = $2",
            progress, goal_id
        )

async def add_goal_task(pool, goal_id: int, title: str) -> Dict[str, Any]:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO goal_tasks (goal_id, title)
            VALUES ($1, $2)
            RETURNING *
            """,
            goal_id, title
        )
        # Recalculate progress
        await _recalculate_goal_progress(conn, goal_id)
        return dict(row)

async def complete_goal_task(pool, task_id: int) -> None:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "UPDATE goal_tasks SET is_completed = TRUE, completed_at = NOW() WHERE id = $1 RETURNING goal_id",
            task_id
        )
        if row:
            await _recalculate_goal_progress(conn, row['goal_id'])

async def get_goal_with_tasks(pool, goal_id: int) -> Optional[Dict[str, Any]]:
    async with pool.acquire() as conn:
        goal = await conn.fetchrow("SELECT * FROM goals WHERE id = $1", goal_id)
        if not goal:
            return None
        
        tasks = await conn.fetch("SELECT * FROM goal_tasks WHERE goal_id = $1 ORDER BY created_at ASC", goal_id)
        res = dict(goal)
        res['tasks'] = [dict(t) for t in tasks]
        return res

async def _recalculate_goal_progress(conn, goal_id: int) -> None:
    stats = await conn.fetchrow(
        """
        SELECT 
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE is_completed = TRUE) as completed
        FROM goal_tasks
        WHERE goal_id = $1
        """,
        goal_id
    )
    
    if stats['total'] > 0:
        progress = int((stats['completed'] / stats['total']) * 100)
    else:
        progress = 0
        
    await conn.execute("UPDATE goals SET progress = $1, updated_at = NOW() WHERE id = $2", progress, goal_id)

async def get_goal_by_title(pool, title: str) -> Optional[Dict[str, Any]]:
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM goals WHERE title ILIKE $1 AND status = 'active' LIMIT 1", f"%{title}%")
        return dict(row) if row else None

async def get_goal_task_by_title(pool, goal_id: int, title: str) -> Optional[Dict[str, Any]]:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM goal_tasks WHERE goal_id = $1 AND title ILIKE $2 AND is_completed = FALSE LIMIT 1",
            goal_id, f"%{title}%"
        )
        return dict(row) if row else None

async def get_goals_progress_delta(pool) -> list:
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT title, progress, status, deadline
            FROM goals
            WHERE status = 'active'
            ORDER BY progress DESC
        """)
        return [dict(r) for r in rows]
