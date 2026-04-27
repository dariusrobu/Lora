# db/queries/history.py
from datetime import datetime, timedelta
from typing import List, Dict, Any


async def save_message(pool, user_id: int, role: str, content: str) -> None:
    """Saves a message to the history."""
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO message_history (user_id, role, content)
            VALUES ($1, $2, $3)
            """,
            user_id,
            role,
            content,
        )


async def get_recent_history(
    pool, user_id: int, limit: int = 8
) -> List[Dict[str, Any]]:
    """Retrieves the last N messages for a specific user."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT role, content 
            FROM message_history 
            WHERE user_id = $1 
            ORDER BY created_at DESC 
            LIMIT $2
            """,
            user_id,
            limit,
        )
        # Return in chronological order
        return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]


async def cleanup_history(pool, days: int = 30) -> int:
    """Deletes history older than N days."""
    cutoff = datetime.now() - timedelta(days=days)
    async with pool.acquire() as conn:
        res = await conn.execute(
            "DELETE FROM message_history WHERE created_at < $1", cutoff
        )
        # res is like "DELETE 5"
        try:
            return int(res.split(" ")[1])
        except Exception:
            return 0


async def search_history(
    pool, user_id: int, query: str, limit: int = 5
) -> List[Dict[str, Any]]:
    """Searches the message history using full-text search."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT role, content, created_at
            FROM message_history
            WHERE user_id = $1 AND to_tsvector('simple', content) @@ to_tsquery('simple', $2)
            ORDER BY created_at DESC
            LIMIT $3
            """,
            user_id,
            " & ".join(query.split()),  # Simple AND-based query
            limit,
        )
        return [dict(r) for r in rows]
