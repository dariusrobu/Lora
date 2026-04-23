# db/queries/university_schedules.py
"""DB queries for schedule imports: schedule rows and academic_periods."""
from datetime import date
from typing import Any, Dict, List, Optional


async def insert_schedule_row(
    pool,
    day_of_week: int,
    start_time: str,
    end_time: str,
    subject_name: str,
    class_type: str,
    room: Optional[str],
    week_type: str,
) -> None:
    """Inserts a single schedule row; ignores duplicates."""
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO schedule
                (day_of_week, start_time, end_time, subject_name, class_type, room, week_type)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT DO NOTHING
            """,
            day_of_week,
            start_time,
            end_time,
            subject_name,
            class_type,
            room,
            week_type,
        )


async def insert_academic_period(
    pool,
    academic_year: str,
    semester: int,
    period_type: str,
    start_date: date,
    end_date: date,
    description: Optional[str],
) -> None:
    """Inserts an academic period; ignores duplicates."""
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO academic_periods
                (academic_year, semester, period_type, start_date, end_date, description)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT DO NOTHING
            """,
            academic_year,
            semester,
            period_type,
            start_date,
            end_date,
            description,
        )


async def list_academic_periods(
    pool, academic_year: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Returns academic periods, optionally filtered by year."""
    async with pool.acquire() as conn:
        if academic_year:
            rows = await conn.fetch(
                "SELECT * FROM academic_periods WHERE academic_year = $1 ORDER BY start_date",
                academic_year,
            )
        else:
            rows = await conn.fetch(
                "SELECT * FROM academic_periods ORDER BY academic_year DESC, start_date"
            )
        return [dict(r) for r in rows]
