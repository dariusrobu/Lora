from typing import List, Optional, Dict, Any
from datetime import date

async def get_all_goals(pool) -> List[Dict[str, Any]]:
    # Toate goals active grupate pe categorie + count sub-tasks
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT g.*, 
                   (SELECT COUNT(*) FROM goal_tasks WHERE goal_id = g.id) as total_tasks,
                   (SELECT COUNT(*) FROM goal_tasks WHERE goal_id = g.id AND is_completed = TRUE) as completed_tasks
            FROM goals g
            WHERE g.status = 'active'
            ORDER BY g.category ASC, g.created_at DESC
            """
        )
        return [dict(r) for r in rows]

async def get_goal_by_id(pool, goal_id: int) -> Optional[Dict[str, Any]]:
    async with pool.acquire() as conn:
        goal = await conn.fetchrow("SELECT * FROM goals WHERE id = $1", goal_id)
        if not goal:
            return None
        
        tasks = await conn.fetch("SELECT * FROM goal_tasks WHERE goal_id = $1 ORDER BY created_at ASC", goal_id)
        res = dict(goal)
        res['tasks'] = [dict(t) for t in tasks]
        return res

async def get_completed_goals(pool) -> List[Dict[str, Any]]:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM goals WHERE status = 'completed' ORDER BY updated_at DESC LIMIT 50"
        )
        return [dict(r) for r in rows]

async def add_goal(pool, title: str, description: Optional[str], category: str) -> Dict[str, Any]:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO goals (title, description, category, status, progress)
            VALUES ($1, $2, $3, 'active', 0)
            RETURNING *
            """,
            title, description, category
        )
        return dict(row)

async def update_goal(pool, goal_id: int, title: str, description: Optional[str], category: str) -> Optional[Dict[str, Any]]:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE goals 
            SET title = $1, description = $2, category = $3, updated_at = NOW()
            WHERE id = $4
            RETURNING *
            """,
            title, description, category, goal_id
        )
        return dict(row) if row else None

async def update_goal_progress(pool, goal_id: int) -> int:
    async with pool.acquire() as conn:
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
        
        progress = 0
        if stats['total'] > 0:
            progress = int((stats['completed'] / stats['total']) * 100)
            
        await conn.execute("UPDATE goals SET progress = $1, updated_at = NOW() WHERE id = $2", progress, goal_id)
        return progress

async def complete_goal(pool, goal_id: int) -> bool:
    async with pool.acquire() as conn:
        res = await conn.execute(
            "UPDATE goals SET status = 'completed', progress = 100, updated_at = NOW() WHERE id = $1",
            goal_id
        )
        return res.endswith("1")

async def delete_goal(pool, goal_id: int) -> bool:
    async with pool.acquire() as conn:
        # Delete dependencies first
        await conn.execute("DELETE FROM goal_tasks WHERE goal_id = $1", goal_id)
        res = await conn.execute("DELETE FROM goals WHERE id = $1", goal_id)
        return res.endswith("1")

async def add_subtask(pool, goal_id: int, title: str) -> Dict[str, Any]:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO goal_tasks (goal_id, title, is_completed)
            VALUES ($1, $2, FALSE)
            RETURNING *
            """,
            goal_id, title
        )
    await update_goal_progress(pool, goal_id)
    return dict(row)

async def complete_subtask(pool, subtask_id: int) -> bool:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE goal_tasks 
            SET is_completed = NOT is_completed, completed_at = CASE WHEN NOT is_completed THEN NOW() ELSE NULL END
            WHERE id = $1 
            RETURNING goal_id
            """,
            subtask_id
        )
        if row:
            await update_goal_progress(pool, row['goal_id'])
            return True
        return False

async def delete_subtask(pool, subtask_id: int) -> bool:
    async with pool.acquire() as conn:
        row = await conn.fetchrow("DELETE FROM goal_tasks WHERE id = $1 RETURNING goal_id", subtask_id)
        if row:
            await update_goal_progress(pool, row['goal_id'])
            return True
        return False

async def get_goals_overview(pool) -> Dict[str, Any]:
    async with pool.acquire() as conn:
        active = await conn.fetchval("SELECT COUNT(*) FROM goals WHERE status = 'active'")
        completed = await conn.fetchval("SELECT COUNT(*) FROM goals WHERE status = 'completed'")
        at_risk = await conn.fetchval("SELECT COUNT(*) FROM goals WHERE status = 'active' AND updated_at < NOW() - INTERVAL '14 days'")
        
        cats = await conn.fetch(
            """
            SELECT category, 
                   COUNT(*) FILTER (WHERE status = 'active') as active_count,
                   COUNT(*) FILTER (WHERE status = 'completed') as completed_count,
                   COUNT(*) FILTER (WHERE status = 'active' AND updated_at < NOW() - INTERVAL '14 days') as risk_count
            FROM goals
            GROUP BY category
            """
        )
        
        return {
            'total_active': active,
            'total_completed': completed,
            'total_risk': at_risk,
            'categories': [dict(c) for c in cats]
        }
