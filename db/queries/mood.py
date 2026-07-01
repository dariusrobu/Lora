from typing import List, Dict, Any, Optional
from datetime import date

MOOD_MAP = {
    "great": 5,
    "good": 4,
    "neutral": 3,
    "okay": 3,
    "bad": 2,
    "terrible": 1,
    "awful": 1,
}


async def get_monthly_mood_data(pool, year: int, month: int) -> List[Dict[str, Any]]:
    """Fetches and maps mood data from journal_entries and notes for a specific month."""
    async with pool.acquire() as conn:
        # Fetch from journal_entries
        journals = await conn.fetch(
            """
            SELECT entry_date as log_date, mood 
            FROM journal_entries 
            WHERE EXTRACT(YEAR FROM entry_date) = $1 AND EXTRACT(MONTH FROM entry_date) = $2
            AND mood IS NOT NULL
            """,
            year,
            month,
        )

        # Fetch from notes (type='journal')
        notes = await conn.fetch(
            """
            SELECT created_at::date as log_date, mood 
            FROM notes 
            WHERE type = 'journal' 
            AND EXTRACT(YEAR FROM created_at) = $1 AND EXTRACT(MONTH FROM created_at) = $2
            AND mood IS NOT NULL
            """,
            year,
            month,
        )

        # Merge data (day as key)
        merged = {}
        for r in list(journals) + list(notes):
            d = r["log_date"]
            m_val = MOOD_MAP.get(r["mood"].lower(), 3)
            # If multiple for a day, take the max (most positive) or average? Let's take latest (by merging)
            merged[d] = m_val

        # Convert to sorted list of dicts
        result = []
        for d in sorted(merged.keys()):
            result.append({"date": d, "value": merged[d]})

        return result


async def get_weekly_mood_summary(
    pool, start_date: date, end_date: date
) -> Dict[str, int]:
    """Returns counts of each mood label for the weekly summary."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT mood, COUNT(*) as count 
            FROM (
                SELECT mood FROM journal_entries WHERE entry_date BETWEEN $1 AND $2 AND mood IS NOT NULL
                UNION ALL
                SELECT mood FROM notes WHERE type = 'journal' AND created_at::date BETWEEN $1 AND $2 AND mood IS NOT NULL
            ) combined
            GROUP BY mood
            """,
            start_date,
            end_date,
        )
        return {r["mood"]: r["count"] for r in rows}


async def log_mood(pool, mood: str, notes: Optional[str] = None, log_date: Optional[str] = None) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO journal_entries (entry_date, mood, reflection_text)
            VALUES ($1, $2, $3)
            ON CONFLICT (entry_date) DO UPDATE SET mood = EXCLUDED.mood, reflection_text = COALESCE(EXCLUDED.reflection_text, journal_entries.reflection_text)
            """,
            log_date or date.today().isoformat(),
            mood,
            notes,
        )


async def delete_mood(pool, log_date: str) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM journal_entries WHERE entry_date = $1",
            log_date,
        )
