from typing import List, Dict, Any

async def save_feedback(pool, intent_used: str, user_correction: str):
    """Saves negative feedback to the database."""
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO feedback (intent_used, user_correction) VALUES ($1, $2)",
            intent_used,
            user_correction
        )

async def get_recent_feedback(pool, limit: int = 10) -> List[Dict[str, Any]]:
    """Retrieves the most recent negative feedbacks."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, intent_used, user_correction, created_at FROM feedback ORDER BY created_at DESC LIMIT $1",
            limit
        )
        return [dict(r) for r in rows]

async def get_weekly_feedback_count(pool) -> int:
    """Returns the number of negative feedbacks in the last 7 days."""
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "SELECT COUNT(*) FROM feedback WHERE created_at > NOW() - INTERVAL '7 days'"
        )
