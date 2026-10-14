"""Materialize academic timetable rules as dated calendar occurrences."""

import uuid
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import asyncpg

from lora_v2.config import Settings

ACADEMIC_NAMESPACE = uuid.UUID("af8d8802-7508-4b89-b1fa-f7f39ed6ba32")


def _week_type(day: date, semester_start: date, vacations: list[tuple[date, date]]) -> str:
    start_monday = semester_start - timedelta(days=semester_start.weekday())
    target_monday = day - timedelta(days=day.weekday())
    vacation_days = 0
    for begins, ends in vacations:
        clipped_start = max(begins, start_monday)
        clipped_end = min(ends, target_monday - timedelta(days=1))
        if clipped_end >= clipped_start:
            vacation_days += (clipped_end - clipped_start).days + 1
    week_number = ((target_monday - start_monday).days - vacation_days) // 7 + 1
    return "odd" if week_number % 2 else "even"


async def materialize_schedule(
    pool: asyncpg.Pool,
    settings: Settings,
    owner_id: int,
    start: date | None = None,
    days: int = 60,
) -> int:
    """Refresh upcoming academic occurrences without touching Obsidian or n8n."""
    beginning = start or datetime.now(ZoneInfo(settings.timezone)).date()
    async with pool.acquire() as conn:
        semester = await conn.fetchrow(
            "SELECT semester_start,semester_end FROM academic_semesters WHERE owner_id=$1", owner_id
        )
        if not semester:
            return 0
        rules = await conn.fetch(
            """SELECT r.id,r.title,r.day_of_week,r.start_time,r.end_time,r.week_type,
            r.class_type,r.room,r.valid_from,r.valid_until
            FROM academic_schedule_rules r LEFT JOIN academic_subjects s ON s.id=r.subject_id
            WHERE r.owner_id=$1 AND r.is_active=true AND (s.id IS NULL OR s.is_active=true)""",
            owner_id,
        )
        vacation_rows = await conn.fetch(
            "SELECT starts_on,ends_on FROM academic_vacations WHERE owner_id=$1", owner_id
        )
        vacations = [(row["starts_on"], row["ends_on"]) for row in vacation_rows]
        inserted = 0
        expected_ids: set[uuid.UUID] = set()
        async with conn.transaction():
            for offset in range(days):
                day = beginning + timedelta(days=offset)
                if day < semester["semester_start"] or (semester["semester_end"] and day > semester["semester_end"]):
                    continue
                if any(starts <= day <= ends for starts, ends in vacations):
                    continue
                parity = _week_type(day, semester["semester_start"], vacations)
                for rule in rules:
                    if rule["day_of_week"] != day.weekday():
                        continue
                    if rule["week_type"] not in ("both", parity):
                        continue
                    if rule["valid_from"] and day < rule["valid_from"]:
                        continue
                    if rule["valid_until"] and day > rule["valid_until"]:
                        continue
                    starts_at = datetime.combine(day, rule["start_time"], ZoneInfo(settings.timezone))
                    ends_at = datetime.combine(day, rule["end_time"], ZoneInfo(settings.timezone))
                    title = f"{rule['title']} · {rule['class_type']}" if rule["class_type"] else rule["title"]
                    occurrence_id = uuid.uuid5(ACADEMIC_NAMESPACE, f"{owner_id}:{rule['id']}:{day.isoformat()}")
                    expected_ids.add(occurrence_id)
                    affected = await conn.fetchval(
                        """INSERT INTO calendar_entries(id,owner_id,kind,title,starts_at,ends_at,notes,legacy_source)
                        VALUES ($1,$2,'academic',$3,$4,$5,$6,'academic_rule')
                        ON CONFLICT (id) DO UPDATE SET status='active',title=EXCLUDED.title,starts_at=EXCLUDED.starts_at,
                        ends_at=EXCLUDED.ends_at,notes=EXCLUDED.notes,version=calendar_entries.version+1,
                        updated_at=now()
                        WHERE calendar_entries.title IS DISTINCT FROM EXCLUDED.title
                        OR calendar_entries.starts_at IS DISTINCT FROM EXCLUDED.starts_at
                        OR calendar_entries.ends_at IS DISTINCT FROM EXCLUDED.ends_at
                        OR calendar_entries.notes IS DISTINCT FROM EXCLUDED.notes
                        OR calendar_entries.status != 'active'
                        RETURNING id""",
                        occurrence_id, owner_id, title, starts_at, ends_at, rule["room"],
                    )
                    if affected:
                        inserted += 1
            window_start = datetime.combine(beginning, datetime.min.time(), ZoneInfo(settings.timezone))
            window_end = datetime.combine(beginning + timedelta(days=days), datetime.min.time(), ZoneInfo(settings.timezone))
            await conn.execute(
                """UPDATE calendar_entries SET status='cancelled',version=version+1,updated_at=now()
                WHERE owner_id=$1 AND kind='academic' AND legacy_source='academic_rule'
                AND status='active' AND starts_at >= $2 AND starts_at < $3
                AND NOT (id = ANY($4::uuid[]))""",
                owner_id, window_start, window_end, list(expected_ids),
            )
    return inserted
