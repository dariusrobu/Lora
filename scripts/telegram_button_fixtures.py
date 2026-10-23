"""Seed and hide one clearly labelled owner-only Telegram button test set."""

import argparse
import asyncio
import hashlib
import json
import uuid
from datetime import datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import asyncpg

from lora_v2.academic_calendar import ACADEMIC_NAMESPACE
from lora_v2.config import Settings
from lora_v2.db import create_pool


NAMESPACE = uuid.UUID("09cd8b96-60fd-4188-8df0-72fe4adc2e94")
PREFIX = "🧪 TEST Lora — "


def _id(owner_id: int, name: str) -> uuid.UUID:
    return uuid.uuid5(NAMESPACE, f"telegram-buttons-2026-10-23:{owner_id}:{name}")


async def seed(pool: asyncpg.Pool, settings: Settings) -> dict[str, int]:
    owner = settings.telegram_user_id
    now = datetime.now(ZoneInfo(settings.timezone))
    day = now.date()
    ids = {name: _id(owner, name) for name in (
        "project", "task", "reminder", "event", "subject", "rule", "news", "forum", "category",
        "expense", "workout",
    )}
    academic_id = uuid.uuid5(ACADEMIC_NAMESPACE, f"{owner}:{ids['rule']}:{day.isoformat()}")
    reminder_at = datetime.combine(day, time(19, 30), ZoneInfo(settings.timezone))
    if reminder_at <= now + timedelta(hours=2):
        reminder_at = now + timedelta(hours=3)
    event_at = datetime.combine(day + timedelta(days=1), time(18), ZoneInfo(settings.timezone))
    class_at = datetime.combine(day, time(10), ZoneInfo(settings.timezone))
    news_title = PREFIX + "anunț pentru Citit/Arhivează"
    news_body = "Acesta este un anunț fictiv pentru testarea butoanelor Telegram."
    news_hash = hashlib.sha256((news_title + news_body).encode()).hexdigest()
    forum_title = PREFIX + "forum pentru Citit/Arhivează"
    forum_body = "Acesta este un mesaj de forum fictiv pentru testarea butoanelor Telegram."
    forum_hash = hashlib.sha256((forum_title + forum_body).encode()).hexdigest()
    inserted: dict[str, int] = {}
    async with pool.acquire() as conn:
        async with conn.transaction():
            statements: tuple[tuple[str, str, tuple[object, ...]], ...] = (
                ("project", """INSERT INTO projects(id,owner_id,name) VALUES ($1,$2,$3)
                    ON CONFLICT (id) DO NOTHING RETURNING id""",
                 (ids["project"], owner, PREFIX + "proiect")),
                ("task", """INSERT INTO tasks(id,owner_id,title,project_id,notes)
                    VALUES ($1,$2,$3,$4,$5) ON CONFLICT (id) DO NOTHING RETURNING id""",
                 (ids["task"], owner, PREFIX + "task pentru Gata/Mâine", ids["project"],
                  "Fictiv. Fără termen și fără alertă inițială.")),
                ("reminder", """INSERT INTO calendar_entries
                    (id,owner_id,kind,title,starts_at,notes,legacy_source)
                    VALUES ($1,$2,'reminder',$3,$4,$5,'telegram_button_test')
                    ON CONFLICT (id) DO NOTHING RETURNING id""",
                 (ids["reminder"], owner, PREFIX + "reminder pentru Gata/+1 oră/Mâine",
                  reminder_at, "Fictiv. Fără alertă inițială.")),
                ("event", """INSERT INTO calendar_entries
                    (id,owner_id,kind,title,starts_at,ends_at,notes,legacy_source)
                    VALUES ($1,$2,'event',$3,$4,$5,$6,'telegram_button_test')
                    ON CONFLICT (id) DO NOTHING RETURNING id""",
                 (ids["event"], owner, PREFIX + "eveniment de calendar", event_at,
                  event_at + timedelta(hours=1), "Fictiv; exclus din sincronizarea Apple Calendar.")),
                ("subject", """INSERT INTO academic_subjects(id,owner_id,name)
                    VALUES ($1,$2,$3) ON CONFLICT (id) DO NOTHING RETURNING id""",
                 (ids["subject"], owner, PREFIX + "materie")),
                ("rule", """INSERT INTO academic_schedule_rules
                    (id,owner_id,subject_id,title,day_of_week,start_time,end_time,
                     class_type,room,valid_from,valid_until)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,'Seminar','TEST',$8,$8)
                    ON CONFLICT (id) DO NOTHING RETURNING id""",
                 (ids["rule"], owner, ids["subject"], PREFIX + "prezență",
                  day.weekday(), class_at.timetz().replace(tzinfo=None),
                  (class_at + timedelta(hours=1)).timetz().replace(tzinfo=None), day)),
                ("academic", """INSERT INTO calendar_entries
                    (id,owner_id,kind,title,starts_at,ends_at,notes,legacy_source)
                    VALUES ($1,$2,'academic',$3,$4,$5,'TEST','academic_rule')
                    ON CONFLICT (id) DO NOTHING RETURNING id""",
                 (academic_id, owner, PREFIX + "prezență · Seminar", class_at,
                  class_at + timedelta(hours=1))),
                ("news", """INSERT INTO moodle_posts
                    (id,owner_id,course_url,course_title,forum_title,kind,discussion_url,
                     title,body,content_hash)
                    VALUES ($1,$2,$3,$4,'Anunțuri','announcement',$5,$6,$7,$8)
                    ON CONFLICT (id) DO NOTHING RETURNING id""",
                 (ids["news"], owner, "https://example.invalid/lora-button-test",
                  PREFIX + "materie", f"https://example.invalid/lora-button-test/{ids['news']}",
                  news_title, news_body, news_hash)),
                ("forum", """INSERT INTO moodle_posts
                    (id,owner_id,course_url,course_title,forum_title,kind,discussion_url,
                     title,body,content_hash)
                    VALUES ($1,$2,$3,$4,'Forum TEST','forum',$5,$6,$7,$8)
                    ON CONFLICT (id) DO NOTHING RETURNING id""",
                 (ids["forum"], owner, "https://example.invalid/lora-button-test",
                  PREFIX + "materie", f"https://example.invalid/lora-button-test/{ids['forum']}",
                  forum_title, forum_body, forum_hash)),
                ("category", """INSERT INTO expense_categories(id,owner_id,name)
                    VALUES ($1,$2,$3) ON CONFLICT (id) DO NOTHING RETURNING id""",
                 (ids["category"], owner, PREFIX + "categorie")),
                ("expense", """INSERT INTO expenses
                    (id,owner_id,amount,currency,category,merchant,description,spent_at)
                    VALUES ($1,$2,$3,'RON',$4,$5,$6,$7)
                    ON CONFLICT (id) DO NOTHING RETURNING id""",
                 (ids["expense"], owner, Decimal("1.23"), PREFIX + "categorie",
                  "TEST Lora", PREFIX + "cheltuială pentru categorie", now)),
                ("workout", """INSERT INTO workouts
                    (id,owner_id,started_at,duration_minutes,activity,notes)
                    VALUES ($1,$2,$3,15,$4,$5)
                    ON CONFLICT (id) DO NOTHING RETURNING id""",
                 (ids["workout"], owner, now, PREFIX + "antrenament",
                  "Fictiv; doar pentru testarea listei.")),
            )
            for name, sql, args in statements:
                inserted[name] = int(await conn.fetchval(sql, *args) is not None)
    return inserted


async def cleanup(pool: asyncpg.Pool, settings: Settings) -> dict[str, int]:
    """Hide test entries and queue Apple deletion if a button synced them."""
    owner = settings.telegram_user_id
    ids = {name: _id(owner, name) for name in (
        "project", "task", "reminder", "event", "subject", "rule", "news", "forum", "category",
        "expense", "workout",
    )}
    counts: dict[str, int] = {}
    async with pool.acquire() as conn:
        async with conn.transaction():
            for name in ("task", "reminder", "event"):
                if name == "task":
                    row = await conn.fetchrow(
                        "SELECT version,title FROM tasks WHERE id=$1 AND owner_id=$2",
                        ids[name], owner,
                    )
                else:
                    row = await conn.fetchrow(
                        "SELECT version,title FROM calendar_entries WHERE id=$1 AND owner_id=$2",
                        ids[name], owner,
                    )
                if not row or not row["title"].startswith(PREFIX):
                    counts[name] = 0
                    continue
                if name == "task":
                    result = await conn.execute(
                        """UPDATE tasks SET status='cancelled',version=version+1,updated_at=now()
                        WHERE id=$1 AND owner_id=$2 AND status!='cancelled'""", ids[name], owner,
                    )
                else:
                    result = await conn.execute(
                        """UPDATE calendar_entries SET status='cancelled',version=version+1,
                        updated_at=now() WHERE id=$1 AND owner_id=$2 AND status!='cancelled'""",
                        ids[name], owner,
                    )
                counts[name] = int(result.endswith("1"))
                if name in {"task", "reminder"} and counts[name]:
                    entity_type = "task" if name == "task" else "calendar_entry"
                    await conn.execute(
                        """INSERT INTO notification_outbox
                        (id,owner_id,dedupe_key,channel,kind,payload)
                        VALUES ($1,$2,$3,'apple','delete',$4::jsonb)
                        ON CONFLICT DO NOTHING""",
                        uuid.uuid4(), owner,
                        f"{entity_type}:{ids[name]}:test_cleanup:{row['version'] + 1}",
                        json.dumps({"entity_type": entity_type,
                                    "entity_id": str(ids[name]), "operation": "delete"}),
                    )
            await conn.execute(
                """UPDATE alert_occurrences SET status='cancelled'
                WHERE owner_id=$1 AND entry_id=$2 AND status='pending'""", owner, ids["reminder"],
            )
            rule_day = await conn.fetchval(
                "SELECT valid_from FROM academic_schedule_rules WHERE id=$1 AND owner_id=$2",
                ids["rule"], owner,
            )
            academic_id = (uuid.uuid5(ACADEMIC_NAMESPACE, f"{owner}:{ids['rule']}:{rule_day.isoformat()}")
                           if rule_day else None)
            await conn.execute(
                "DELETE FROM academic_attendance WHERE schedule_rule_id=$1 AND owner_id=$2",
                ids["rule"], owner,
            )
            if academic_id:
                await conn.execute(
                    """DELETE FROM calendar_entries WHERE id=$1 AND owner_id=$2
                    AND kind='academic' AND title=$3""",
                    academic_id, owner, PREFIX + "prezență · Seminar",
                )
            await conn.execute("DELETE FROM academic_schedule_rules WHERE id=$1 AND owner_id=$2", ids["rule"], owner)
            await conn.execute("DELETE FROM academic_subjects WHERE id=$1 AND owner_id=$2", ids["subject"], owner)
            await conn.execute("DELETE FROM moodle_posts WHERE id=$1 AND owner_id=$2", ids["news"], owner)
            await conn.execute("DELETE FROM moodle_posts WHERE id=$1 AND owner_id=$2", ids["forum"], owner)
            await conn.execute("DELETE FROM expenses WHERE id=$1 AND owner_id=$2", ids["expense"], owner)
            await conn.execute("DELETE FROM workouts WHERE id=$1 AND owner_id=$2", ids["workout"], owner)
            await conn.execute("DELETE FROM expense_categories WHERE id=$1 AND owner_id=$2", ids["category"], owner)
            await conn.execute(
                "UPDATE projects SET status='archived',version=version+1,updated_at=now() "
                "WHERE id=$1 AND owner_id=$2 AND name=$3 AND status!='archived'",
                ids["project"], owner, PREFIX + "proiect",
            )
    return counts


async def main() -> None:
    parser = argparse.ArgumentParser(description="Manage the labelled Telegram button test data")
    parser.add_argument("action", choices=("seed", "cleanup"))
    args = parser.parse_args()
    settings = Settings.from_env()
    pool = await create_pool(settings)
    try:
        result = await (seed(pool, settings) if args.action == "seed" else cleanup(pool, settings))
        print(args.action, result)
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
