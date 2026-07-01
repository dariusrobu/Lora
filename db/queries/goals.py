from typing import List, Optional, Dict, Any


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

        tasks = await conn.fetch(
            "SELECT * FROM goal_tasks WHERE goal_id = $1 ORDER BY created_at ASC",
            goal_id,
        )
        res = dict(goal)
        res["tasks"] = [dict(t) for t in tasks]
        return res


async def get_completed_goals(pool) -> List[Dict[str, Any]]:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM goals WHERE status = 'completed' ORDER BY updated_at DESC LIMIT 50"
        )
        return [dict(r) for r in rows]


async def add_goal(
    pool,
    title: str,
    description: Optional[str],
    category: str,
    time_horizon: str = "month",
    linked_keywords: list = None,
) -> int:
    import json

    kw_json = json.dumps(linked_keywords) if linked_keywords else "[]"
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO goals (title, description, category, status, progress, time_horizon, linked_keywords)
            VALUES ($1, $2, $3, 'active', 0, $4, $5::jsonb)
            RETURNING id
            """,
            title,
            description,
            category,
            time_horizon,
            kw_json,
        )
        return row["id"]


async def update_goal(
    pool, goal_id: int, **kwargs
) -> Optional[Dict[str, Any]]:
    allowed = {"title", "description", "category", "status", "progress", "time_horizon", "linked_keywords"}
    updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
    if not updates:
        return None
    set_clauses = ", ".join(f"{k} = ${i+1}" for i, k in enumerate(updates))
    values = list(updates.values())
    values.append(goal_id)
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"UPDATE goals SET {set_clauses}, updated_at = NOW() WHERE id = ${len(values)} RETURNING *",
            *values,
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
            goal_id,
        )

        progress = 0
        if stats["total"] > 0:
            progress = int((stats["completed"] / stats["total"]) * 100)

        await conn.execute(
            "UPDATE goals SET progress = $1, updated_at = NOW() WHERE id = $2",
            progress,
            goal_id,
        )
        return progress


async def complete_goal(pool, goal_id: int) -> bool:
    async with pool.acquire() as conn:
        res = await conn.execute(
            "UPDATE goals SET status = 'completed', progress = 100, updated_at = NOW() WHERE id = $1",
            goal_id,
        )
        return res.endswith("1")


async def delete_goal(pool, goal_id: int) -> bool:
    async with pool.acquire() as conn:
        # Delete dependencies first
        await conn.execute("DELETE FROM goal_tasks WHERE goal_id = $1", goal_id)
        res = await conn.execute("DELETE FROM goals WHERE id = $1", goal_id)
        return res.endswith("1")


async def add_subtask(pool, goal_id: int, title: str) -> int:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO goal_tasks (goal_id, title, is_completed)
            VALUES ($1, $2, FALSE)
            RETURNING id
            """,
            goal_id,
            title,
        )
    await update_goal_progress(pool, goal_id)
    return row["id"]


async def complete_subtask(pool, subtask_id: int) -> bool:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE goal_tasks 
            SET is_completed = NOT is_completed, completed_at = CASE WHEN NOT is_completed THEN NOW() ELSE NULL END
            WHERE id = $1 
            RETURNING goal_id
            """,
            subtask_id,
        )
        if row:
            await update_goal_progress(pool, row["goal_id"])
            return True
        return False


async def delete_subtask(pool, subtask_id: int) -> bool:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "DELETE FROM goal_tasks WHERE id = $1 RETURNING goal_id", subtask_id
        )
        if row:
            await update_goal_progress(pool, row["goal_id"])
            return True
        return False


async def get_goals_overview(pool) -> Dict[str, Any]:
    async with pool.acquire() as conn:
        active = await conn.fetchval(
            "SELECT COUNT(*) FROM goals WHERE status = 'active'"
        )
        completed = await conn.fetchval(
            "SELECT COUNT(*) FROM goals WHERE status = 'completed'"
        )
        at_risk = await conn.fetchval(
            "SELECT COUNT(*) FROM goals WHERE status = 'active' AND updated_at < NOW() - INTERVAL '14 days'"
        )

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
            "total_active": active,
            "total_completed": completed,
            "total_risk": at_risk,
            "categories": [dict(c) for c in cats],
        }


async def check_goal_alignment(pool, user_id: int) -> Optional[str]:
    """Checks if there's a goal that needs alignment and returns a recommendation string."""
    async with pool.acquire() as conn:
        # Find active goals with linked_keywords
        goals = await conn.fetch(
            "SELECT title, linked_keywords FROM goals WHERE status = 'active' ORDER BY updated_at ASC LIMIT 5"
        )
        if not goals:
            return None

        import json

        for goal in goals:
            try:
                keywords = json.loads(goal["linked_keywords"])
                if keywords and isinstance(keywords, list):
                    return f"Azi poți avansa spre obiectivul '{goal['title']}': adaugă un task legat de {', '.join(keywords[:2])}."
            except Exception:
                pass

        # Fallback to the most neglected goal
        return f"Azi poți avansa spre obiectivul '{goals[0]['title']}'. Nu l-ai mai actualizat demult."
