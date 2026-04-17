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
            entry_date,
            reflection_text,
            mood,
            tomorrow_focus,
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


async def get_mood_range(
    pool, start_date: date, end_date: date
) -> List[Dict[str, Any]]:
    """Return mood entries within date range, newest first."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT entry_date as date, mood
            FROM journal_entries
            WHERE entry_date >= $1 AND entry_date <= $2
            ORDER BY entry_date DESC
            """,
            start_date,
            end_date,
        )
        return [dict(r) for r in rows if r["mood"]]


async def get_mood_distribution(
    pool, start_date: date, end_date: date
) -> Dict[str, int]:
    """Return mood frequency counts within date range."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT mood, COUNT(*) as count
            FROM journal_entries
            WHERE entry_date >= $1 AND entry_date <= $2
              AND mood IS NOT NULL
            GROUP BY mood
            """,
            start_date,
            end_date,
        )
        return {r["mood"]: r["count"] for r in rows}
