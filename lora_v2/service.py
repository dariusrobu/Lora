"""Transactional capture and command execution shared by every channel."""

import json
import uuid
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import asyncpg

from lora_v2.config import Settings
from lora_v2.models import (
    ActionResult,
    Command,
    CreateCalendarEntry,
    CreateProject,
    CreateTask,
    LogExpense,
    LogIncome,
    LogMeal,
    LogWorkout,
    LogHealth,
    RescheduleEntry,
    CompleteEntry,
    CompleteTask,
)


def _id() -> uuid.UUID:
    return uuid.uuid4()


async def capture(
    pool: asyncpg.Pool,
    owner_id: int,
    channel: str,
    external_id: str,
    raw_text: str,
    content_type: str = "text",
    attachment_ref: str | None = None,
) -> dict:
    """Persist an ingress message before any model or domain action runs."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO captures(id, owner_id, channel, external_id, raw_text, content_type, attachment_ref)
            VALUES ($1,$2,$3,$4,$5,$6,$7)
            ON CONFLICT (owner_id, channel, external_id)
            DO UPDATE SET external_id=EXCLUDED.external_id
            RETURNING id, status, created_at
            """,
            _id(), owner_id, channel, external_id, raw_text, content_type, attachment_ref,
        )
    return dict(row)


async def execute_command(
    pool: asyncpg.Pool,
    settings: Settings,
    owner_id: int,
    command: Command,
    idempotency_key: str,
    capture_id: uuid.UUID | None = None,
) -> ActionResult:
    """Execute one validated command and write its receipt in the same transaction."""
    payload = command.payload()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                "SELECT pg_advisory_xact_lock(hashtext($1))",
                f"{owner_id}:{idempotency_key}",
            )
            previous = await conn.fetchval(
                "SELECT result FROM action_executions WHERE owner_id=$1 AND idempotency_key=$2",
                owner_id, idempotency_key,
            )
            if previous is not None:
                result = ActionResult.model_validate(json.loads(previous))
                return result.model_copy(update={"status": "already_done"})

            result = await _apply(conn, settings, owner_id, command.type, payload)
            if result.status == "saved":
                await conn.execute(
                    """INSERT INTO action_executions(id,owner_id,idempotency_key,capture_id,command_type,result)
                    VALUES ($1,$2,$3,$4,$5,$6::jsonb)""",
                    _id(), owner_id, idempotency_key, capture_id,
                    command.type, result.model_dump_json(),
                )
            return result


async def _apply(
    conn: asyncpg.Connection,
    settings: Settings,
    owner_id: int,
    command_type: str,
    payload: object,
) -> ActionResult:
    entity_id = _id()
    if command_type == "create_project" and isinstance(payload, CreateProject):
        await conn.execute(
            "INSERT INTO projects(id,owner_id,name) VALUES ($1,$2,$3)",
            entity_id, owner_id, payload.name,
        )
        return ActionResult(status="saved", command_type=command_type, entity_id=str(entity_id), entity_type="project", message=f"Proiect salvat: {payload.name}")

    if command_type == "create_task" and isinstance(payload, CreateTask):
        if payload.project_id:
            project = await conn.fetchval(
                "SELECT id FROM projects WHERE id=$1 AND owner_id=$2", uuid.UUID(payload.project_id), owner_id
            )
            if not project:
                return ActionResult(status="needs_input", command_type=command_type, message="Nu găsesc proiectul ales.")
        await conn.execute(
            "INSERT INTO tasks(id,owner_id,title,notes,project_id,due_at) VALUES ($1,$2,$3,$4,$5,$6)",
            entity_id, owner_id, payload.title, payload.notes,
            uuid.UUID(payload.project_id) if payload.project_id else None, payload.due_at,
        )
        await _enqueue_apple(conn, owner_id, "task", entity_id, "upsert")
        return ActionResult(status="saved", command_type=command_type, entity_id=str(entity_id), entity_type="task", message=f"Task salvat: {payload.title}")

    if command_type == "create_calendar_entry" and isinstance(payload, CreateCalendarEntry):
        if payload.ends_at and payload.ends_at <= payload.starts_at:
            return ActionResult(status="needs_input", command_type=command_type, message="Ora de final trebuie să fie după început.")
        local_start = payload.starts_at.astimezone(ZoneInfo(settings.timezone))
        followup_at = None
        if payload.followup_evening:
            local_followup = datetime.combine(local_start.date(), time(settings.followup_hour), ZoneInfo(settings.timezone))
            if local_followup <= local_start:
                local_followup += timedelta(days=1)
            followup_at = local_followup
        await conn.execute(
            """INSERT INTO calendar_entries(id,owner_id,kind,title,starts_at,ends_at,notes,followup_at)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8)""",
            entity_id, owner_id, payload.kind, payload.title, payload.starts_at,
            payload.ends_at, payload.notes, followup_at,
        )
        for offset in payload.alert_offsets_minutes:
            await conn.execute(
                """INSERT INTO alert_occurrences(id,owner_id,entry_id,alert_at,purpose)
                VALUES ($1,$2,$3,$4,$5)""",
                _id(), owner_id, entity_id,
                payload.starts_at - timedelta(minutes=offset), f"before_{offset}m",
            )
        await _enqueue_apple(conn, owner_id, "calendar_entry", entity_id, "upsert")
        return ActionResult(status="saved", command_type=command_type, entity_id=str(entity_id), entity_type=payload.kind, message=f"{payload.kind.capitalize()} salvat: {payload.title}", details={"alerts": payload.alert_offsets_minutes, "followup_at": followup_at.isoformat() if followup_at else None})

    if command_type == "log_expense" and isinstance(payload, LogExpense):
        category = payload.category
        if payload.merchant:
            learned = await conn.fetchval(
                "SELECT category FROM expense_category_rules WHERE owner_id=$1 AND merchant_key=$2",
                owner_id, payload.merchant.casefold().strip(),
            )
            if (payload.expected_merchant_category is not None and
                    learned != payload.expected_merchant_category):
                return ActionResult(status="needs_input", command_type=command_type,
                    message="Categoria memorată pentru comerciant s-a schimbat între timp. Verifică din nou cheltuiala.")
            category = category if payload.category_override and category else learned or category
        if not category:
            return ActionResult(status="needs_input", command_type=command_type, message="În ce categorie pun cheltuiala?")
        await conn.execute(
            """INSERT INTO expenses(id,owner_id,amount,currency,category,merchant,description,spent_at)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8)""",
            entity_id, owner_id, payload.amount, payload.currency, category,
            payload.merchant, payload.description, payload.spent_at,
        )
        if payload.category_override and payload.merchant:
            await conn.execute(
                """INSERT INTO expense_category_rules(owner_id,merchant_key,category,source_expense_id)
                VALUES ($1,$2,$3,$4) ON CONFLICT (owner_id,merchant_key) DO UPDATE SET
                category=EXCLUDED.category,source_expense_id=EXCLUDED.source_expense_id,updated_at=now()""",
                owner_id, payload.merchant.casefold().strip(), category, entity_id,
            )
        return ActionResult(status="saved", command_type=command_type, entity_id=str(entity_id), entity_type="expense", message=f"Cheltuială salvată: {payload.amount} {payload.currency} · {category}")

    if command_type == "log_income" and isinstance(payload, LogIncome):
        await conn.execute(
            """INSERT INTO incomes(id,owner_id,amount,currency,category,source,description,received_at)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8)""",
            entity_id, owner_id, payload.amount, payload.currency, payload.category,
            payload.source, payload.description, payload.received_at,
        )
        return ActionResult(status="saved", command_type=command_type, entity_id=str(entity_id),
            entity_type="income", message=f"Venit salvat: {payload.amount} {payload.currency}.")

    if command_type == "log_meal" and isinstance(payload, LogMeal):
        await conn.execute(
            """INSERT INTO meals(id,owner_id,eaten_at,description,estimate_source,estimate_uncertain,photo_ref)
            VALUES ($1,$2,$3,$4,$5,$6,$7)""",
            entity_id, owner_id, payload.eaten_at, payload.description,
            payload.estimate_source, payload.estimate_source != "manual", payload.photo_ref,
        )
        for item in payload.items:
            await conn.execute(
                """INSERT INTO meal_items(id,meal_id,name,grams,calories,protein_g,carbs_g,fat_g,
                nutrition_provider,nutrition_source_id,nutrition_source_title,nutrition_source_url)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)""",
                _id(), entity_id, item.name, item.grams, item.calories,
                item.protein_g, item.carbs_g, item.fat_g, item.nutrition_provider,
                item.nutrition_source_id, item.nutrition_source_title, item.nutrition_source_url,
            )
        return ActionResult(status="saved", command_type=command_type, entity_id=str(entity_id), entity_type="meal", message="Masă salvată ca estimare editabilă.")

    if command_type == "log_workout" and isinstance(payload, LogWorkout):
        await conn.execute(
            """INSERT INTO workouts(id,owner_id,started_at,duration_minutes,activity,notes)
            VALUES ($1,$2,$3,$4,$5,$6)""",
            entity_id, owner_id, payload.started_at, payload.duration_minutes,
            payload.activity, payload.notes,
        )
        for exercise in payload.exercises:
            await conn.execute(
                """INSERT INTO workout_exercises(id,workout_id,name,sets,reps,weight_kg)
                VALUES ($1,$2,$3,$4,$5,$6)""",
                _id(), entity_id, exercise.name, exercise.sets, exercise.reps, exercise.weight_kg,
            )
        return ActionResult(status="saved", command_type=command_type, entity_id=str(entity_id), entity_type="workout", message=f"Antrenament salvat: {payload.activity}, {payload.duration_minutes} min.")

    if command_type == "log_health" and isinstance(payload, LogHealth):
        row = await conn.fetchrow(
            """INSERT INTO health_entries(id,owner_id,log_date,sleep_hours,sleep_quality,water_ml,
            weight_kg,cigarettes,notes)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
            ON CONFLICT (owner_id,log_date) WHERE deleted_at IS NULL DO UPDATE SET
            sleep_hours=COALESCE(EXCLUDED.sleep_hours,health_entries.sleep_hours),
            sleep_quality=COALESCE(EXCLUDED.sleep_quality,health_entries.sleep_quality),
            water_ml=COALESCE(health_entries.water_ml,0)+COALESCE(EXCLUDED.water_ml,0),
            weight_kg=COALESCE(EXCLUDED.weight_kg,health_entries.weight_kg),
            cigarettes=COALESCE(health_entries.cigarettes,0)+COALESCE(EXCLUDED.cigarettes,0),
            notes=COALESCE(EXCLUDED.notes,health_entries.notes),
            version=health_entries.version+1,updated_at=now()
            RETURNING id,version""",
            entity_id, owner_id, payload.log_date, payload.sleep_hours,
            payload.sleep_quality, payload.water_ml_delta, payload.weight_kg,
            payload.cigarettes_delta, payload.notes,
        )
        return ActionResult(status="saved", command_type=command_type,
            entity_id=str(row["id"]), entity_type="health",
            message=f"Sănătate actualizată pentru {payload.log_date.isoformat()}.",
            details={"version": row["version"]})

    if command_type == "reschedule_entry" and isinstance(payload, RescheduleEntry):
        old = await conn.fetchrow(
            "SELECT followup_at FROM calendar_entries WHERE id=$1 AND owner_id=$2",
            payload.entry_id, owner_id,
        )
        followup_at = None
        if old and old["followup_at"] is not None:
            new_local = payload.starts_at.astimezone(ZoneInfo(settings.timezone))
            followup_at = datetime.combine(new_local.date(), time(settings.followup_hour), ZoneInfo(settings.timezone))
            if followup_at <= new_local:
                followup_at += timedelta(days=1)
        old_offsets = await conn.fetch(
            "SELECT DISTINCT purpose FROM alert_occurrences WHERE entry_id=$1 AND purpose LIKE 'before_%'",
            payload.entry_id,
        )
        row = await conn.fetchrow(
            """UPDATE calendar_entries SET starts_at=$4,followup_at=$5,version=version+1,updated_at=now()
            WHERE id=$1 AND owner_id=$2 AND version=$3 AND status='active'
            RETURNING title,kind,version""",
            payload.entry_id, owner_id, payload.expected_version, payload.starts_at, followup_at,
        )
        if not row:
            return ActionResult(status="needs_input", command_type=command_type, message="Reminderul s-a schimbat între timp. Verifică ora actuală.")
        await conn.execute("UPDATE alert_occurrences SET status='cancelled' WHERE entry_id=$1 AND status='pending'", payload.entry_id)
        for offset_row in old_offsets or [{"purpose": "before_0m"}]:
            purpose = offset_row["purpose"]
            offset = int(purpose.removeprefix("before_").removesuffix("m"))
            await conn.execute(
                """INSERT INTO alert_occurrences(id,owner_id,entry_id,alert_at,purpose)
                VALUES ($1,$2,$3,$4,$5) ON CONFLICT DO NOTHING""",
                _id(), owner_id, payload.entry_id,
                payload.starts_at - timedelta(minutes=offset), purpose,
            )
        await _enqueue_apple(conn, owner_id, "calendar_entry", payload.entry_id, f"upsert:{row['version']}")
        return ActionResult(status="saved", command_type=command_type, entity_id=str(payload.entry_id), entity_type=row["kind"], message=f"Am mutat {row['title']}.")

    if command_type == "complete_entry" and isinstance(payload, CompleteEntry):
        row = await conn.fetchrow(
            """UPDATE calendar_entries SET status='done',version=version+1,updated_at=now()
            WHERE id=$1 AND owner_id=$2 AND version=$3 AND status='active'
            RETURNING title,kind,version""",
            payload.entry_id, owner_id, payload.expected_version,
        )
        if not row:
            return ActionResult(status="needs_input", command_type=command_type, message="Elementul s-a schimbat între timp.")
        await conn.execute("UPDATE alert_occurrences SET status='cancelled' WHERE entry_id=$1 AND status='pending'", payload.entry_id)
        await _enqueue_apple(conn, owner_id, "calendar_entry", payload.entry_id, f"upsert:{row['version']}")
        return ActionResult(status="saved", command_type=command_type, entity_id=str(payload.entry_id), entity_type=row["kind"], message=f"Am marcat {row['title']} ca făcut.")

    if command_type == "complete_task" and isinstance(payload, CompleteTask):
        row = await conn.fetchrow(
            """UPDATE tasks SET status='done',version=version+1,updated_at=now()
            WHERE id=$1 AND owner_id=$2 AND version=$3 AND status='pending'
            RETURNING title,version""",
            payload.task_id, owner_id, payload.expected_version,
        )
        if not row:
            return ActionResult(status="needs_input", command_type=command_type, message="Taskul s-a schimbat între timp.")
        await _enqueue_apple(conn, owner_id, "task", payload.task_id, f"upsert:{row['version']}")
        return ActionResult(status="saved", command_type=command_type, entity_id=str(payload.task_id), entity_type="task", message=f"Gata: {row['title']}")

    raise ValueError(f"Unsupported command: {command_type}")


async def _enqueue_apple(
    conn: asyncpg.Connection, owner_id: int, entity_type: str, entity_id: uuid.UUID, operation: str
) -> None:
    await conn.execute(
        """INSERT INTO notification_outbox(id,owner_id,dedupe_key,channel,kind,payload)
        VALUES ($1,$2,$3,'apple',$4,$5::jsonb)
        ON CONFLICT (owner_id,dedupe_key,channel) DO NOTHING""",
        _id(), owner_id, f"{entity_type}:{entity_id}:{operation}:1", operation,
        json.dumps({"entity_type": entity_type, "entity_id": str(entity_id), "operation": operation}),
    )
