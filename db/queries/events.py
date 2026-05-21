from typing import List, Optional, Dict, Any
from datetime import date, time


async def add_event(
    pool,
    title: str,
    event_date: date,
    event_time: Optional[time] = None,
    description: Optional[str] = None,
    project_id: Optional[int] = None,
    is_recurring: bool = False,
    recurrence: Optional[str] = None,
    remind_before_minutes: int = 30,
    event_type: str = "event",
) -> int:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO events (title, event_date, event_time, description, project_id, is_recurring, recurrence, remind_before_minutes, event_type)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            RETURNING id
            """,
            title,
            event_date,
            event_time,
            description,
            project_id,
            is_recurring,
            recurrence,
            remind_before_minutes,
            event_type,
        )
        return row["id"]


async def add_event_with_1day_reminder(
    pool,
    title: str,
    event_date: date,
    event_time: Optional[time] = None,
    description: Optional[str] = None,
    project_id: Optional[int] = None,
    is_recurring: bool = False,
    recurrence: Optional[str] = None,
    remind_before_minutes: int = 30,
    event_type: str = "event",
) -> int:
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                """
                INSERT INTO events (title, event_date, event_time, description, project_id, is_recurring, recurrence, remind_before_minutes, remind_1day, event_type)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, TRUE, $9)
                RETURNING id
                """,
                title,
                event_date,
                event_time,
                description,
                project_id,
                is_recurring,
                recurrence,
                remind_before_minutes,
                event_type,
            )
            event_id = row["id"]

            await conn.execute(
                """
                INSERT INTO event_day_reminders (event_id, event_date, sent)
                VALUES ($1, $2, FALSE)
                ON CONFLICT DO NOTHING
                """,
                event_id,
                event_date,
            )
            return event_id


async def list_events(
    pool, start_date: date, end_date: Optional[date] = None
) -> List[Dict[str, Any]]:
    async with pool.acquire() as conn:
        if not end_date:
            rows = await conn.fetch(
                "SELECT * FROM events WHERE event_type = 'event' AND event_date >= $1 ORDER BY event_date, event_time",
                start_date,
            )
        else:
            rows = await conn.fetch(
                "SELECT * FROM events WHERE event_type = 'event' AND event_date BETWEEN $1 AND $2 ORDER BY event_date, event_time",
                start_date,
                end_date,
            )
        return [dict(r) for r in rows]


async def list_reminders(pool) -> List[Dict[str, Any]]:
    """List all upcoming reminders."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM events WHERE event_type = 'reminder' AND event_date >= CURRENT_DATE ORDER BY event_date, event_time"
        )
        return [dict(r) for r in rows]


async def delete_event_by_title(pool, title: str, event_type: str = "event") -> int:
    """Delete an event/reminder by title. Returns number of rows deleted."""
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM events WHERE LOWER(title) = LOWER($1) AND event_type = $2",
            title,
            event_type,
        )
        return int(result.split()[-1]) if result else 0


async def get_events_needing_reminder(
    pool, minutes_before: int = 30
) -> List[Dict[str, Any]]:
    """Get events and reminders that need notification."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT e.* FROM events e
            WHERE (
                -- 1. Events with time-based reminders (standard window)
                (e.event_type = 'event' AND e.event_time IS NOT NULL
                  AND e.reminded_at IS NULL
                  AND e.event_date = CURRENT_DATE
                  AND e.remind_before_minutes > 0
                  AND (e.event_time - INTERVAL '1 minute' * e.remind_before_minutes)
                      BETWEEN (CURRENT_TIMESTAMP AT TIME ZONE 'Europe/Bucharest')::time - INTERVAL '15 minutes'
                              AND (CURRENT_TIMESTAMP AT TIME ZONE 'Europe/Bucharest')::time + INTERVAL '15 minutes')
                OR
                -- 2. Reminders with specific time (standard window)
                (e.event_type = 'reminder' AND e.event_time IS NOT NULL
                  AND e.reminded_at IS NULL
                  AND e.event_date = CURRENT_DATE
                  AND (CURRENT_TIMESTAMP AT TIME ZONE 'Europe/Bucharest')::time
                      BETWEEN e.event_time - INTERVAL '15 minutes' AND e.event_time + INTERVAL '15 minutes')
                OR
                -- 3. CATCH-UP: Reminders/Events from last 2 hours that were MISSED (bot was down)
                (e.reminded_at IS NULL
                  AND e.event_date = CURRENT_DATE
                  AND e.event_time IS NOT NULL
                  AND (CURRENT_TIMESTAMP AT TIME ZONE 'Europe/Bucharest')::time > e.event_time
                  AND (CURRENT_TIMESTAMP AT TIME ZONE 'Europe/Bucharest')::time < e.event_time + INTERVAL '2 hours')
                OR
                -- 4. Reminders without specific time (morning slot)
                (e.event_type = 'reminder' AND e.event_time IS NULL
                  AND e.reminded_at IS NULL
                  AND e.event_date = CURRENT_DATE
                  AND (CURRENT_TIMESTAMP AT TIME ZONE 'Europe/Bucharest')::time
                      BETWEEN '08:55'::time AND '09:15'::time)
            )
            ORDER BY e.event_time NULLS LAST
            """
        )
        return [dict(r) for r in rows]


async def mark_event_reminded(pool, event_id: int) -> None:
    """Mark that time-based reminder was sent."""
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE events SET reminded_at = NOW() WHERE id = $1", event_id
        )


async def get_events_for_day_reminder(
    pool, reminder_date: date
) -> List[Dict[str, Any]]:
    """Get events that need 1-day reminder for the given date."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT e.* FROM events e
            JOIN event_day_reminders edr ON e.id = edr.event_id AND e.event_date = edr.event_date
            WHERE e.event_date = $1
              AND e.remind_1day = TRUE
              AND edr.sent = FALSE
            ORDER BY e.event_time
            """,
            reminder_date,
        )
        return [dict(r) for r in rows]


async def mark_day_reminder_sent(pool, event_id: int, event_date: date) -> None:
    """Mark that 1-day reminder was sent."""
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO event_day_reminders (event_id, event_date, sent)
            VALUES ($1, $2, TRUE)
            ON CONFLICT (event_id, event_date) 
            DO UPDATE SET sent = TRUE
            """,
            event_id,
            event_date,
        )


async def update_event_reminder(
    pool, event_id: int, remind_before_minutes: int
) -> None:
    """Update the reminder minutes for an event."""
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE events SET remind_before_minutes = $1, reminded_at = NULL WHERE id = $2",
            remind_before_minutes,
            event_id,
        )


async def toggle_1day_reminder(
    pool, event_id: int, event_date: date, enable: bool
) -> None:
    """Enable or disable 1-day reminder for an event."""
    async with pool.acquire() as conn:
        if enable:
            await conn.execute(
                """
                UPDATE events SET remind_1day = TRUE WHERE id = $1;
                INSERT INTO event_day_reminders (event_id, event_date, sent)
                VALUES ($1, $2, FALSE)
                ON CONFLICT (event_id, event_date) DO UPDATE SET sent = FALSE
                """,
                event_id,
                event_date,
            )
        else:
            await conn.execute(
                """
                UPDATE events SET remind_1day = FALSE WHERE id = $1;
                DELETE FROM event_day_reminders WHERE event_id = $1 AND event_date = $2
                """,
                event_id,
                event_date,
            )


async def delete_event(pool, event_id: int):
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM events WHERE id = $1", event_id)
