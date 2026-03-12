from typing import List, Optional, Dict, Any
from datetime import date, time

async def add_event(pool, title: str, event_date: date, event_time: Optional[time] = None, description: Optional[str] = None, project_id: Optional[int] = None, is_recurring: bool = False, recurrence: Optional[str] = None) -> int:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO events (title, event_date, event_time, description, project_id, is_recurring, recurrence)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING id
            """,
            title, event_date, event_time, description, project_id, is_recurring, recurrence
        )
        return row['id']

async def list_events(pool, start_date: date, end_date: Optional[date] = None) -> List[Dict[str, Any]]:
    async with pool.acquire() as conn:
        if not end_date:
            rows = await conn.fetch(
                "SELECT * FROM events WHERE event_date >= $1 ORDER BY event_date, event_time",
                start_date
            )
        else:
            rows = await conn.fetch(
                "SELECT * FROM events WHERE event_date BETWEEN $1 AND $2 ORDER BY event_date, event_time",
                start_date, end_date
            )
        return [dict(r) for r in rows]

async def delete_event(pool, event_id: int):
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM events WHERE id = $1", event_id)
