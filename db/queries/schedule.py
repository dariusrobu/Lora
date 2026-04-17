# db/queries/schedule.py

from datetime import date, datetime, timedelta
import pytz


async def get_current_week_type(pool) -> str:
    """Returnează 'odd' sau 'even' bazat pe săptămâna curentă din semestru.

    Ține cont de vacanțe — zilele de vacanță nu sunt numărate în calculul săptămânii.
    """
    async with pool.acquire() as conn:
        config = await conn.fetchrow(
            "SELECT semester_start FROM semester_config ORDER BY id DESC LIMIT 1"
        )

    if not config:
        return "odd"

    today = date.today()
    semester_start = config["semester_start"]

    if today < semester_start:
        return "odd"

    # Calculează zilele totale din semestru
    total_days = (today - semester_start).days + 1

    # Scade zilele de vacanță care au trecut
    vacations = await get_all_vacations(pool)
    vacation_days = 0
    for v in vacations:
        if v["end_date"] < semester_start:
            continue
        if v["start_date"] > today:
            continue

        # Perioada se suprapune cu semestru până azi
        v_start = max(v["start_date"], semester_start)
        v_end = min(v["end_date"], today)
        if v_end >= v_start:
            vacation_days += (v_end - v_start).days + 1

    # Săptămâna efectivă de curs
    effective_days = total_days - vacation_days
    week_number = effective_days // 7 + 1

    return "odd" if week_number % 2 == 1 else "even"


async def get_today_schedule(pool) -> list:
    """Returnează orarul de azi filtrat după săptămână pară/impară."""
    today = date.today()
    day_of_week = today.weekday()  # 0=Luni, 4=Vineri

    if day_of_week > 4:  # Weekend
        return []

    week_type = await get_current_week_type(pool)

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT DISTINCT ON (start_time, subject_name, room) * FROM schedule
            WHERE day_of_week = $1
              AND is_active = TRUE
              AND (week_type = 'both' OR week_type = $2)
            ORDER BY start_time ASC, subject_name ASC, room ASC
        """,
            day_of_week,
            week_type,
        )
    return [dict(r) for r in rows]


async def get_week_schedule(pool) -> tuple:
    """Returnează orarul săptămânii curente."""
    week_type = await get_current_week_type(pool)

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT DISTINCT ON (day_of_week, start_time, subject_name, room) * FROM schedule
            WHERE is_active = TRUE
              AND (week_type = 'both' OR week_type = $1)
            ORDER BY day_of_week ASC, start_time ASC, subject_name ASC, room ASC
        """,
            week_type,
        )

    days = {0: "Luni", 1: "Marți", 2: "Miercuri", 3: "Joi", 4: "Vineri"}
    result = {i: [] for i in range(5)}
    for row in rows:
        result[row["day_of_week"]].append(dict(row))
    return result, days, week_type


async def get_upcoming_classes(pool, minutes_ahead=20) -> list:
    """Returnează cursurile care încep în următoarele X minute."""
    today = date.today()
    if today.weekday() > 4:
        return []

    from core.config import TIMEZONE

    user_tz = pytz.timezone(TIMEZONE)
    now = datetime.now(user_tz)
    target_time = (
        (now + timedelta(minutes=minutes_ahead)).time().replace(second=0, microsecond=0)
    )
    now_time = now.time().replace(second=0, microsecond=0)

    week_type = await get_current_week_type(pool)

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT DISTINCT ON (start_time, subject_name, room) * FROM schedule
            WHERE day_of_week = $1
              AND is_active = TRUE
              AND (week_type = 'both' OR week_type = $2)
              AND start_time > $3
              AND start_time <= $4
            ORDER BY start_time ASC, subject_name ASC, room ASC
        """,
            today.weekday(),
            week_type,
            now_time,
            target_time,
        )
    return [dict(r) for r in rows]


async def is_reminder_sent(pool, schedule_id, reminder_date) -> bool:
    """Verifică dacă s-a trimis deja reminder pentru un curs azi."""
    async with pool.acquire() as conn:
        exists = await conn.fetchval(
            """
            SELECT EXISTS (
                SELECT 1 FROM schedule_reminders_sent 
                WHERE schedule_id = $1 AND reminder_date = $2
            )
        """,
            schedule_id,
            reminder_date,
        )
        return exists


async def log_reminder_sent(pool, schedule_id, reminder_date) -> None:
    """Înregistrează trimiterea unui reminder."""
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO schedule_reminders_sent (schedule_id, reminder_date)
            VALUES ($1, $2)
            ON CONFLICT (schedule_id, reminder_date) DO NOTHING
        """,
            schedule_id,
            reminder_date,
        )


async def get_schedule_by_id(pool, schedule_id: int) -> dict | None:
    """Returnează un curs după ID."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM schedule WHERE id = $1", schedule_id)
        return dict(row) if row else None


async def is_vacation(pool, check_date: date | None = None) -> bool:
    """Returnează True dacă data este într-o perioadă de vacanță activă."""
    if check_date is None:
        check_date = date.today()

    async with pool.acquire() as conn:
        exists = await conn.fetchval(
            """
            SELECT EXISTS (
                SELECT 1 FROM vacation_periods
                WHERE is_active = TRUE
                  AND start_date <= $1
                  AND end_date >= $1
            )
        """,
            check_date,
        )
        return bool(exists)


async def get_active_vacation(pool, check_date: date | None = None) -> dict | None:
    """Returnează perioada de vacanță activă pentru o dată, sau None."""
    if check_date is None:
        check_date = date.today()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT * FROM vacation_periods
            WHERE is_active = TRUE
              AND start_date <= $1
              AND end_date >= $1
            LIMIT 1
            """,
            check_date,
        )
        return dict(row) if row else None


async def add_vacation_period(pool, name: str, start_date: date, end_date: date) -> int:
    """Adaugă o perioadă de vacanță nouă."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO vacation_periods (name, start_date, end_date)
            VALUES ($1, $2, $3)
            RETURNING id
            """,
            name,
            start_date,
            end_date,
        )
        return row["id"]


async def delete_vacation(pool, vacation_id: int) -> None:
    """Șterge o perioadă de vacanță."""
    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM vacation_periods WHERE id = $1",
            vacation_id,
        )


async def get_all_vacations(pool) -> list:
    """Returnează toate perioadele de vacanță."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM vacation_periods ORDER BY start_date ASC"
        )
        return [dict(r) for r in rows]
