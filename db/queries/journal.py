from typing import Optional, Dict, Any, List
from datetime import date


async def save_journal_entry(
    pool,
    entry_date: date,
    reflection_text: str,
    mood: str,
    tomorrow_focus: str,
) -> None:
    """Insert or update a journal entry for the given date."""
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO journal_entries (entry_date, reflection_text, mood, tomorrow_focus)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (entry_date) DO UPDATE
                SET reflection_text = EXCLUDED.reflection_text,
                    mood            = EXCLUDED.mood,
                    tomorrow_focus  = EXCLUDED.tomorrow_focus,
                    created_at      = NOW()
            """,
            entry_date, reflection_text, mood, tomorrow_focus,
        )


async def get_journal_entry(pool, entry_date: date) -> Optional[Dict[str, Any]]:
    """Return a single journal entry for the given date, or None."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM journal_entries WHERE entry_date = $1",
            entry_date,
        )
        return dict(row) if row else None


async def get_recent_journal_entries(pool, limit: int = 7) -> List[Dict[str, Any]]:
    """Return the most recent N journal entries, newest first."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM journal_entries
            ORDER BY entry_date DESC
            LIMIT $1
            """,
            limit,
        )
        return [dict(r) for r in rows]
