"""Read-only legacy extraction into the isolated v2 database.

Dry-run is the default. The legacy connection is explicitly read-only.
"""

import argparse
import asyncio
import json
import os
import uuid
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import asyncpg

from lora_v2.config import Settings
from lora_v2.db import create_pool, migrate

NAMESPACE = uuid.UUID("535c90c8-2474-44de-b99d-733204658506")


def _stable_uuid(table: str, old_id: int, owner_id: int) -> uuid.UUID:
    return uuid.uuid5(NAMESPACE, f"{owner_id}:{table}:{old_id}")


def _datetime(value: date | datetime | None, tz: ZoneInfo, at: time = time(12, 0)) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=tz) if value.tzinfo is None else value.astimezone(tz)
    return datetime.combine(value, at, tz)


QUERIES = {
    "projects": "SELECT * FROM projects ORDER BY id",
    "tasks": "SELECT * FROM tasks ORDER BY id",
    "events": "SELECT * FROM events ORDER BY id",
    "finances": "SELECT * FROM finances ORDER BY id",
    "meals": "SELECT * FROM meals ORDER BY id",
    "meal_items": "SELECT * FROM meal_items ORDER BY id",
    "workouts": "SELECT * FROM workouts ORDER BY id",
    "workout_exercises": "SELECT * FROM workout_exercises ORDER BY id",
    "health_logs": "SELECT * FROM health_logs ORDER BY id",
    "sport_types": "SELECT * FROM sport_types ORDER BY id",
    "subjects": "SELECT * FROM subjects ORDER BY id",
    "schedule": "SELECT * FROM schedule ORDER BY id",
    "attendances": "SELECT * FROM attendances ORDER BY id",
    "grades": "SELECT * FROM grades ORDER BY id",
    "exams": "SELECT * FROM exams ORDER BY id",
    "semester_config": "SELECT * FROM semester_config ORDER BY id",
    "vacation_periods": "SELECT * FROM vacation_periods ORDER BY id",
}


async def read_legacy(source: asyncpg.Pool) -> dict[str, list[dict[str, Any]]]:
    data: dict[str, list[dict[str, Any]]] = {}
    async with source.acquire() as conn:
        async with conn.transaction(readonly=True):
            for table, query in QUERIES.items():
                exists = await conn.fetchval("SELECT to_regclass($1)", f"public.{table}")
                data[table] = [dict(row) for row in await conn.fetch(query)] if exists else []
    return data


async def import_legacy(
    target: asyncpg.Pool,
    settings: Settings,
    owner_id: int,
    data: dict[str, list[dict[str, Any]]],
) -> dict[str, int]:
    """Insert history idempotently; never overwrite records edited in v2."""
    tz = ZoneInfo(settings.timezone)
    counts: dict[str, int] = {}

    def _uuid(table: str, old_id: int) -> uuid.UUID:
        return _stable_uuid(table, old_id, owner_id)

    async with target.acquire() as conn:
        async with conn.transaction():
            for row in data["projects"]:
                await conn.execute(
                    """INSERT INTO projects(id,owner_id,name,status,legacy_id,created_at,updated_at)
                    VALUES ($1,$2,$3,$4,$5,$6,$7) ON CONFLICT (owner_id,legacy_id) DO NOTHING""",
                    _uuid("projects", row["id"]), owner_id, row["name"], row.get("status") or "active",
                    row["id"], _datetime(row.get("created_at"), tz) or datetime.now(tz),
                    _datetime(row.get("updated_at"), tz) or datetime.now(tz),
                )
            counts["projects"] = len(data["projects"])

            for row in data["subjects"]:
                await conn.execute(
                    """INSERT INTO academic_subjects(id,owner_id,name,professor,credits,is_active,legacy_id)
                    VALUES ($1,$2,$3,$4,$5,$6,$7) ON CONFLICT (owner_id,legacy_id) DO NOTHING""",
                    _uuid("subjects", row["id"]), owner_id, row["name"], row.get("professor"),
                    row.get("credits"), row.get("is_active", True), row["id"],
                )
            counts["subjects"] = len(data["subjects"])

            for row in data["tasks"]:
                due_time = row.get("due_time") or time(12, 0)
                due_at = _datetime(row.get("due_date"), tz, due_time)
                status = row.get("status") or "pending"
                if row.get("deleted_at") is not None:
                    status = "cancelled"
                await conn.execute(
                    """INSERT INTO tasks(id,owner_id,title,notes,project_id,due_at,status,legacy_id,created_at,updated_at)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
                    ON CONFLICT (owner_id,legacy_id) DO NOTHING""",
                    _uuid("tasks", row["id"]), owner_id, row["title"],
                    row.get("notes") or row.get("description"),
                    _uuid("projects", row["project_id"]) if row.get("project_id") else None,
                    due_at, status, row["id"],
                    _datetime(row.get("created_at"), tz) or datetime.now(tz),
                    _datetime(row.get("updated_at"), tz) or datetime.now(tz),
                )
            counts["tasks"] = len(data["tasks"])

            now = datetime.now(tz)
            for row in data["events"]:
                begins = _datetime(row["event_date"], tz, row.get("event_time") or time(9, 0))
                entry_id = _uuid("events", row["id"])
                await conn.execute(
                    """INSERT INTO calendar_entries(id,owner_id,kind,title,starts_at,notes,legacy_source,legacy_id,all_day,created_at,updated_at)
                    VALUES ($1,$2,$3,$4,$5,$6,'events',$7,$8,$9,$10)
                    ON CONFLICT (owner_id,legacy_source,legacy_id) DO NOTHING""",
                    entry_id, owner_id, row.get("event_type") or "event", row["title"], begins,
                    row.get("description"), row["id"], row.get("event_time") is None,
                    _datetime(row.get("created_at"), tz) or now,
                    _datetime(row.get("updated_at"), tz) or now,
                )
                if begins and begins >= now and row.get("reminded_at") is None:
                    offsets = [0]
                    before = row.get("remind_before_minutes")
                    if before and row.get("pre_reminded_at") is None:
                        offsets.append(int(before))
                    for offset in offsets:
                        await conn.execute(
                            """INSERT INTO alert_occurrences(id,owner_id,entry_id,alert_at,purpose)
                            VALUES ($1,$2,$3,$4,$5) ON CONFLICT DO NOTHING""",
                            uuid.uuid4(), owner_id, entry_id,
                            begins - timedelta(minutes=offset), f"before_{offset}m",
                        )
            counts["events"] = len(data["events"])

            for row in data["finances"]:
                if row.get("type") != "expense":
                    continue
                if not row.get("amount") or row["amount"] <= 0:
                    await conn.execute(
                        """INSERT INTO legacy_import_exceptions(owner_id,source_table,legacy_id,reason,source_data)
                        VALUES ($1,'finances',$2,'non_positive_expense',$3::jsonb)
                        ON CONFLICT (owner_id,source_table,legacy_id) DO NOTHING""",
                        owner_id, row["id"], json.dumps(row, default=str),
                    )
                    continue
                await conn.execute(
                    """INSERT INTO expenses(id,owner_id,amount,currency,category,description,spent_at,receipt_ref,legacy_id,created_at,updated_at)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
                    ON CONFLICT (owner_id,legacy_id) DO NOTHING""",
                    _uuid("finances", row["id"]), owner_id, row["amount"], row.get("currency") or "RON",
                    row.get("category") or "altele", row.get("description"),
                    _datetime(row.get("tx_date"), tz) or now, row.get("receipt_local_path"), row["id"],
                    _datetime(row.get("created_at"), tz) or now,
                    _datetime(row.get("updated_at"), tz) or now,
                )
            counts["expenses"] = sum(1 for row in data["finances"] if row.get("type") == "expense" and row.get("amount") and row["amount"] > 0)
            counts["expense_exceptions"] = sum(1 for row in data["finances"] if row.get("type") == "expense" and (not row.get("amount") or row["amount"] <= 0))

            for row in data["finances"]:
                if row.get("type") != "income":
                    continue
                if not row.get("amount") or row["amount"] <= 0:
                    await conn.execute(
                        """INSERT INTO legacy_import_exceptions(owner_id,source_table,legacy_id,reason,source_data)
                        VALUES ($1,'finances',$2,'non_positive_income',$3::jsonb)
                        ON CONFLICT (owner_id,source_table,legacy_id) DO NOTHING""",
                        owner_id, row["id"], json.dumps(row, default=str),
                    )
                    continue
                await conn.execute(
                    """INSERT INTO incomes(id,owner_id,amount,currency,category,description,
                    received_at,legacy_id,created_at,updated_at)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
                    ON CONFLICT (owner_id,legacy_id) DO NOTHING""",
                    _uuid("finances", row["id"]), owner_id, row["amount"],
                    row.get("currency") or "RON", row.get("category"), row.get("description"),
                    _datetime(row.get("tx_date"), tz) or now, row["id"],
                    _datetime(row.get("created_at"), tz) or now,
                    _datetime(row.get("updated_at"), tz) or now,
                )
            counts["incomes"] = sum(1 for row in data["finances"] if row.get("type") == "income" and row.get("amount") and row["amount"] > 0)

            for row in data["meals"]:
                meal_id = _uuid("meals", row["id"])
                await conn.execute(
                    """INSERT INTO meals(id,owner_id,eaten_at,description,estimate_source,estimate_uncertain,legacy_id,created_at,updated_at)
                    VALUES ($1,$2,$3,$4,'text',true,$5,$6,$7)
                    ON CONFLICT (owner_id,legacy_id) DO NOTHING""",
                    meal_id, owner_id, _datetime(row.get("meal_date"), tz) or now,
                    row.get("description"), row["id"], _datetime(row.get("created_at"), tz) or now,
                    _datetime(row.get("created_at"), tz) or now,
                )
            for row in data["meal_items"]:
                await conn.execute(
                    """INSERT INTO meal_items(id,meal_id,name,grams,calories,protein_g,carbs_g,fat_g)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8) ON CONFLICT (id) DO NOTHING""",
                    _uuid("meal_items", row["id"]), _uuid("meals", row["meal_id"]),
                    row["food_name"], row.get("quantity_g"), row.get("calories"),
                    row.get("protein"), row.get("carbs"), row.get("fat"),
                )
            counts["meals"] = len(data["meals"])

            sports = {row["id"]: row["name"] for row in data["sport_types"]}
            for row in data["workouts"]:
                duration = row.get("duration_min")
                await conn.execute(
                    """INSERT INTO workouts(id,owner_id,started_at,duration_minutes,activity,notes,legacy_id,created_at,updated_at)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
                    ON CONFLICT (owner_id,legacy_id) DO NOTHING""",
                    _uuid("workouts", row["id"]), owner_id,
                    _datetime(row.get("workout_date"), tz) or now,
                    duration if duration and duration > 0 else None,
                    sports.get(row.get("sport_id"), "Antrenament"), row.get("notes"), row["id"],
                    _datetime(row.get("created_at"), tz) or now,
                    _datetime(row.get("created_at"), tz) or now,
                )
            for row in data["workout_exercises"]:
                await conn.execute(
                    """INSERT INTO workout_exercises(id,workout_id,name,sets,reps,weight_kg,legacy_id)
                    VALUES ($1,$2,$3,$4,$5,$6,$7) ON CONFLICT (workout_id,legacy_id) DO NOTHING""",
                    _uuid("workout_exercises", row["id"]), _uuid("workouts", row["workout_id"]),
                    row.get("name") or "Exercițiu", row.get("sets"), row.get("reps"),
                    row.get("weight_kg"), row["id"],
                )
            counts["workouts"] = len(data["workouts"])

            for row in data.get("health_logs", []):
                await conn.execute(
                    """INSERT INTO health_entries(id,owner_id,log_date,sleep_hours,sleep_quality,
                    water_ml,weight_kg,cigarettes,notes,legacy_id)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
                    ON CONFLICT (owner_id,legacy_id) DO NOTHING""",
                    _uuid("health_logs", row["id"]), owner_id, row["log_date"],
                    row.get("sleep_hours"), row.get("sleep_quality"), row.get("water_ml"),
                    row.get("weight_kg"), row.get("cigarettes"), row.get("notes"), row["id"],
                )
            counts["health_logs"] = len(data.get("health_logs", []))

            semester_start = data["semester_config"][-1]["semester_start"] if data["semester_config"] else None
            if semester_start:
                await conn.execute(
                    """INSERT INTO academic_semesters(owner_id,semester_start) VALUES ($1,$2)
                    ON CONFLICT (owner_id) DO NOTHING""",
                    owner_id, semester_start,
                )
            for row in data["vacation_periods"]:
                await conn.execute(
                    """INSERT INTO academic_vacations(id,owner_id,name,starts_on,ends_on,legacy_id)
                    VALUES ($1,$2,$3,$4,$5,$6) ON CONFLICT (owner_id,legacy_id) DO NOTHING""",
                    _uuid("vacation_periods", row["id"]), owner_id,
                    row.get("name"), row["start_date"], row["end_date"], row["id"],
                )
            for row in data["schedule"]:
                await conn.execute(
                    """INSERT INTO academic_schedule_rules(id,owner_id,subject_id,title,day_of_week,start_time,end_time,
                    week_type,class_type,room,is_active,legacy_id)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
                    ON CONFLICT (owner_id,legacy_id) DO NOTHING""",
                    _uuid("schedule", row["id"]), owner_id,
                    _uuid("subjects", row["subject_id"]) if row.get("subject_id") else None,
                    row["subject_name"], row["day_of_week"], row["start_time"], row["end_time"],
                    row.get("week_type") or "both", row.get("class_type"), row.get("room"),
                    row.get("is_active", True), row["id"],
                )
            counts["schedule"] = len(data["schedule"])

            for row in data["attendances"]:
                await conn.execute(
                    """INSERT INTO academic_attendance(id,owner_id,subject_id,schedule_rule_id,class_date,attended,notes,legacy_id)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8) ON CONFLICT (owner_id,legacy_id) DO NOTHING""",
                    _uuid("attendances", row["id"]), owner_id,
                    _uuid("subjects", row["subject_id"]) if row.get("subject_id") else None,
                    _uuid("schedule", row["schedule_id"]) if row.get("schedule_id") else None,
                    row["class_date"], row["attended"], row.get("notes"), row["id"],
                )
            counts["attendances"] = len(data["attendances"])

            for row in data["grades"]:
                await conn.execute(
                    """INSERT INTO academic_grades(id,owner_id,subject_id,label,value,recorded_at,legacy_id)
                    VALUES ($1,$2,$3,$4,$5,$6,$7) ON CONFLICT (owner_id,legacy_id) DO NOTHING""",
                    _uuid("grades", row["id"]), owner_id,
                    _uuid("subjects", row["subject_id"]) if row.get("subject_id") else None,
                    row.get("grade_type") or row.get("notes"), row.get("grade"),
                    _datetime(row.get("graded_at"), tz), row["id"],
                )
            counts["grades"] = len(data["grades"])

            for row in data["exams"]:
                await conn.execute(
                    """INSERT INTO academic_exams(id,owner_id,subject_id,title,starts_at,exam_type,room,notes,legacy_id)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9) ON CONFLICT (owner_id,legacy_id) DO NOTHING""",
                    _uuid("exams", row["id"]), owner_id,
                    _uuid("subjects", row["subject_id"]) if row.get("subject_id") else None,
                    row["subject_name"], _datetime(row["exam_date"], tz),
                    row.get("exam_type"), row.get("room"), row.get("notes"), row["id"],
                )
            counts["exams"] = len(data["exams"])
    return counts


async def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only source migration into isolated Lora v2")
    parser.add_argument("--apply", action="store_true", help="Write to LORA_V2_DATABASE_URL after backup restore validation")
    parser.add_argument("--backup-file", type=Path, help="Existing restorable backup of the legacy database")
    args = parser.parse_args()
    settings = Settings.from_env()
    source_url = os.getenv("DATABASE_URL", "")
    if not source_url or source_url == settings.database_url:
        raise ValueError("Legacy DATABASE_URL and LORA_V2_DATABASE_URL must differ")
    if args.apply and (not args.backup_file or not args.backup_file.is_file()):
        raise ValueError("--apply requires a verified --backup-file")
    source = await asyncpg.create_pool(source_url, min_size=1, max_size=2)
    try:
        data = await read_legacy(source)
    finally:
        await source.close()
    print("Legacy row counts:", {table: len(rows) for table, rows in data.items()})
    if not args.apply:
        return
    target = await create_pool(settings)
    try:
        await migrate(target)
        counts = await import_legacy(target, settings, settings.telegram_user_id, data)
        print("Eligible source row counts:", counts)
    finally:
        await target.close()


if __name__ == "__main__":
    asyncio.run(main())
