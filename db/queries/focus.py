# db/queries/focus.py

async def start_session(pool, duration_min, task_description=None) -> int:
    async with pool.acquire() as conn:
        return await conn.fetchval("""
            INSERT INTO focus_sessions (duration_min, task_description)
            VALUES ($1, $2) RETURNING id
        """, duration_min, task_description)

async def complete_session(pool, session_id, task_description=None) -> None:
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE focus_sessions 
            SET completed = TRUE, task_description = COALESCE($1, task_description)
            WHERE id = $2
        """, task_description, session_id)

async def interrupt_session(pool, session_id, interrupted_at) -> None:
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE focus_sessions 
            SET interrupted_at = $1
            WHERE id = $2
        """, interrupted_at, session_id)

async def get_weekly_focus_stats(pool, start_date, end_date) -> dict:
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT 
                COUNT(*) FILTER (WHERE completed = TRUE) as completed_sessions,
                COUNT(*) FILTER (WHERE completed = FALSE AND interrupted_at IS NOT NULL) as interrupted_sessions,
                SUM(duration_min) FILTER (WHERE completed = TRUE) as total_min,
                ROUND(AVG(duration_min) FILTER (WHERE completed = TRUE)) as avg_duration
            FROM focus_sessions
            WHERE session_date >= $1 AND session_date <= $2
        """, start_date, end_date)
        return dict(row) if row else {}

async def get_recent_sessions(pool, days=7) -> list:
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT * FROM focus_sessions
            WHERE session_date >= CURRENT_DATE - $1 * INTERVAL '1 day'
            ORDER BY created_at DESC
        """, days)
        return [dict(r) for r in rows]
