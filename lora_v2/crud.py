"""Explicit, version-checked edits and deletes for the daily domains."""

import json
import uuid
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any, Literal
from zoneinfo import ZoneInfo

import asyncpg
from pydantic import BaseModel, ConfigDict, Field

from lora_v2.models import (
    ActionResult,
    CreateCalendarEntry,
    CreateProject,
    CreateTask,
    LogExpense,
    LogIncome,
    LogMeal,
    LogWorkout,
)
from lora_v2.config import Settings

EntityKind = Literal["project", "task", "calendar_entry", "expense", "income", "meal", "workout", "health"]


class UpdateProject(CreateProject):
    status: Literal["active", "paused", "done", "archived"] = "active"


class UpdateHealth(BaseModel):
    model_config = ConfigDict(extra="forbid")
    log_date: date
    sleep_hours: Decimal | None = Field(default=None, ge=0, le=24)
    sleep_quality: Literal["great", "good", "neutral", "bad", "terrible"] | None = None
    water_ml: int | None = Field(default=None, ge=0)
    weight_kg: Decimal | None = Field(default=None, gt=0, le=500)
    cigarettes: int | None = Field(default=None, ge=0)
    notes: str | None = None


class EditRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    data: dict[str, Any]


MODELS: dict[str, type[BaseModel]] = {
    "project": UpdateProject,
    "task": CreateTask,
    "calendar_entry": CreateCalendarEntry,
    "expense": LogExpense,
    "income": LogIncome,
    "meal": LogMeal,
    "workout": LogWorkout,
    "health": UpdateHealth,
}


async def update_entity(
    pool: asyncpg.Pool,
    settings: Settings,
    owner_id: int,
    kind: EntityKind,
    entity_id: uuid.UUID,
    request: EditRequest,
) -> ActionResult:
    """Replace a whole entity after validating the full edited form."""
    if kind not in MODELS:
        raise ValueError("Unknown entity type")
    payload = MODELS[kind].model_validate(request.data)
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = None
            if kind == "project" and isinstance(payload, UpdateProject):
                row = await conn.fetchrow(
                    """UPDATE projects SET name=$4,status=$5,version=version+1,updated_at=now()
                    WHERE id=$1 AND owner_id=$2 AND version=$3 RETURNING id,version""",
                    entity_id, owner_id, request.expected_version, payload.name, payload.status,
                )
            elif kind == "task" and isinstance(payload, CreateTask):
                project_id = uuid.UUID(payload.project_id) if payload.project_id else None
                if project_id:
                    exists = await conn.fetchval("SELECT 1 FROM projects WHERE id=$1 AND owner_id=$2", project_id, owner_id)
                    if not exists:
                        raise ValueError("Project not found")
                row = await conn.fetchrow(
                    """UPDATE tasks SET title=$4,notes=$5,due_at=$6,project_id=$7,version=version+1,updated_at=now()
                    WHERE id=$1 AND owner_id=$2 AND version=$3 AND status!='cancelled'
                    RETURNING id,version""",
                    entity_id, owner_id, request.expected_version, payload.title,
                    payload.notes, payload.due_at, project_id,
                )
                if row:
                    await _queue_apple(conn, owner_id, kind, entity_id, row["version"], "upsert")
            elif kind == "calendar_entry" and isinstance(payload, CreateCalendarEntry):
                if payload.ends_at and payload.ends_at <= payload.starts_at:
                    raise ValueError("Ora de final trebuie să fie după început")
                followup_at = None
                if payload.followup_evening:
                    local_start = payload.starts_at.astimezone(ZoneInfo(settings.timezone))
                    followup_at = datetime.combine(local_start.date(), time(settings.followup_hour), ZoneInfo(settings.timezone))
                    if followup_at <= local_start:
                        followup_at += timedelta(days=1)
                row = await conn.fetchrow(
                    """UPDATE calendar_entries SET kind=$4,title=$5,starts_at=$6,ends_at=$7,notes=$8,followup_at=$9,
                    version=version+1,updated_at=now()
                    WHERE id=$1 AND owner_id=$2 AND version=$3 AND status='active'
                    RETURNING id,version""",
                    entity_id, owner_id, request.expected_version, payload.kind,
                    payload.title, payload.starts_at, payload.ends_at, payload.notes, followup_at,
                )
                if row:
                    await conn.execute(
                        "UPDATE alert_occurrences SET status='cancelled' WHERE entry_id=$1 AND status='pending'",
                        entity_id,
                    )
                    for offset in payload.alert_offsets_minutes:
                        await conn.execute(
                            """INSERT INTO alert_occurrences(id,owner_id,entry_id,alert_at,purpose)
                            VALUES ($1,$2,$3,$4,$5) ON CONFLICT DO NOTHING""",
                            uuid.uuid4(), owner_id, entity_id,
                            payload.starts_at - timedelta(minutes=offset), f"before_{offset}m",
                        )
                    await _queue_apple(conn, owner_id, kind, entity_id, row["version"], "upsert")
            elif kind == "expense" and isinstance(payload, LogExpense):
                if not payload.category:
                    raise ValueError("Expense category is required for an edit")
                row = await conn.fetchrow(
                    """UPDATE expenses SET amount=$4,currency=$5,category=$6,merchant=$7,
                    description=$8,spent_at=$9,version=version+1,updated_at=now()
                    WHERE id=$1 AND owner_id=$2 AND version=$3 AND deleted_at IS NULL
                    RETURNING id,version""",
                    entity_id, owner_id, request.expected_version, payload.amount,
                    payload.currency, payload.category, payload.merchant,
                    payload.description, payload.spent_at,
                )
                if row and payload.merchant:
                    await conn.execute(
                        """INSERT INTO expense_category_rules(owner_id,merchant_key,category,source_expense_id)
                        VALUES ($1,$2,$3,$4)
                        ON CONFLICT (owner_id,merchant_key) DO UPDATE
                        SET category=EXCLUDED.category,source_expense_id=EXCLUDED.source_expense_id,updated_at=now()""",
                        owner_id, payload.merchant.casefold().strip(), payload.category, entity_id,
                    )
            elif kind == "income" and isinstance(payload, LogIncome):
                row = await conn.fetchrow(
                    """UPDATE incomes SET amount=$4,currency=$5,category=$6,source=$7,
                    description=$8,received_at=$9,version=version+1,updated_at=now()
                    WHERE id=$1 AND owner_id=$2 AND version=$3 AND deleted_at IS NULL
                    RETURNING id,version""",
                    entity_id, owner_id, request.expected_version, payload.amount,
                    payload.currency, payload.category, payload.source,
                    payload.description, payload.received_at,
                )
            elif kind == "meal" and isinstance(payload, LogMeal):
                row = await conn.fetchrow(
                    """UPDATE meals SET eaten_at=$4,description=$5,estimate_source='manual',
                    estimate_uncertain=true,photo_ref=$6,version=version+1,updated_at=now()
                    WHERE id=$1 AND owner_id=$2 AND version=$3 AND deleted_at IS NULL
                    RETURNING id,version""",
                    entity_id, owner_id, request.expected_version,
                    payload.eaten_at, payload.description, payload.photo_ref,
                )
                if row:
                    await conn.execute("DELETE FROM meal_items WHERE meal_id=$1", entity_id)
                    for item in payload.items:
                        await conn.execute(
                            """INSERT INTO meal_items(id,meal_id,name,grams,calories,protein_g,carbs_g,fat_g,
                            nutrition_provider,nutrition_source_id,nutrition_source_title,nutrition_source_url)
                            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)""",
                            uuid.uuid4(), entity_id, item.name, item.grams, item.calories,
                            item.protein_g, item.carbs_g, item.fat_g, item.nutrition_provider,
                            item.nutrition_source_id, item.nutrition_source_title, item.nutrition_source_url,
                        )
            elif kind == "workout" and isinstance(payload, LogWorkout):
                row = await conn.fetchrow(
                    """UPDATE workouts SET started_at=$4,duration_minutes=$5,activity=$6,
                    notes=$7,version=version+1,updated_at=now()
                    WHERE id=$1 AND owner_id=$2 AND version=$3 AND deleted_at IS NULL
                    RETURNING id,version""",
                    entity_id, owner_id, request.expected_version, payload.started_at,
                    payload.duration_minutes, payload.activity, payload.notes,
                )
                if row:
                    await conn.execute("DELETE FROM workout_exercises WHERE workout_id=$1", entity_id)
                    for exercise in payload.exercises:
                        await conn.execute(
                            """INSERT INTO workout_exercises(id,workout_id,name,sets,reps,weight_kg)
                            VALUES ($1,$2,$3,$4,$5,$6)""",
                            uuid.uuid4(), entity_id, exercise.name, exercise.sets,
                            exercise.reps, exercise.weight_kg,
                        )
            elif kind == "health" and isinstance(payload, UpdateHealth):
                row = await conn.fetchrow(
                    """UPDATE health_entries SET log_date=$4,sleep_hours=$5,sleep_quality=$6,
                    water_ml=$7,weight_kg=$8,cigarettes=$9,notes=$10,version=version+1,updated_at=now()
                    WHERE id=$1 AND owner_id=$2 AND version=$3 AND deleted_at IS NULL
                    RETURNING id,version""",
                    entity_id, owner_id, request.expected_version, payload.log_date,
                    payload.sleep_hours, payload.sleep_quality, payload.water_ml,
                    payload.weight_kg, payload.cigarettes, payload.notes,
                )
            if row is None:
                return ActionResult(status="needs_input", command_type=f"update_{kind}", message="Elementul a fost modificat între timp. Reîncarcă-l înainte de editare.")
            return ActionResult(status="saved", command_type=f"update_{kind}", entity_id=str(entity_id), entity_type=kind, message="Modificarea a fost salvată.", details={"version": row["version"]})


async def delete_entity(
    pool: asyncpg.Pool,
    owner_id: int,
    kind: EntityKind,
    entity_id: uuid.UUID,
    expected_version: int,
) -> ActionResult:
    """Soft-delete daily entities, retaining history and the option to restore."""
    statements = {
        "project": "UPDATE projects SET status='archived',version=version+1,updated_at=now() WHERE id=$1 AND owner_id=$2 AND version=$3 AND status!='archived' RETURNING version",
        "task": "UPDATE tasks SET status='cancelled',version=version+1,updated_at=now() WHERE id=$1 AND owner_id=$2 AND version=$3 AND status!='cancelled' RETURNING version",
        "calendar_entry": "UPDATE calendar_entries SET status='cancelled',version=version+1,updated_at=now() WHERE id=$1 AND owner_id=$2 AND version=$3 AND status!='cancelled' RETURNING version",
        "expense": "UPDATE expenses SET deleted_at=now(),version=version+1,updated_at=now() WHERE id=$1 AND owner_id=$2 AND version=$3 AND deleted_at IS NULL RETURNING version",
        "income": "UPDATE incomes SET deleted_at=now(),version=version+1,updated_at=now() WHERE id=$1 AND owner_id=$2 AND version=$3 AND deleted_at IS NULL RETURNING version",
        "meal": "UPDATE meals SET deleted_at=now(),version=version+1,updated_at=now() WHERE id=$1 AND owner_id=$2 AND version=$3 AND deleted_at IS NULL RETURNING version",
        "workout": "UPDATE workouts SET deleted_at=now(),version=version+1,updated_at=now() WHERE id=$1 AND owner_id=$2 AND version=$3 AND deleted_at IS NULL RETURNING version",
        "health": "UPDATE health_entries SET deleted_at=now(),version=version+1,updated_at=now() WHERE id=$1 AND owner_id=$2 AND version=$3 AND deleted_at IS NULL RETURNING version",
    }
    if kind not in statements:
        raise ValueError("Unknown entity type")
    async with pool.acquire() as conn:
        async with conn.transaction():
            version = await conn.fetchval(statements[kind], entity_id, owner_id, expected_version)
            if version is None:
                return ActionResult(status="needs_input", command_type=f"delete_{kind}", message="Elementul a fost modificat între timp. Reîncarcă-l înainte de ștergere.")
            if kind == "calendar_entry":
                await conn.execute(
                    "UPDATE alert_occurrences SET status='cancelled' WHERE entry_id=$1 AND status='pending'",
                    entity_id,
                )
                await _queue_apple(conn, owner_id, kind, entity_id, version, "delete")
            elif kind == "task":
                await _queue_apple(conn, owner_id, kind, entity_id, version, "delete")
            return ActionResult(status="saved", command_type=f"delete_{kind}", entity_id=str(entity_id), entity_type=kind, message="Elementul a fost șters.", details={"version": version})


async def _queue_apple(
    conn: asyncpg.Connection,
    owner_id: int,
    kind: str,
    entity_id: uuid.UUID,
    version: int,
    operation: str,
) -> None:
    await conn.execute(
        """INSERT INTO notification_outbox(id,owner_id,dedupe_key,channel,kind,payload)
        VALUES ($1,$2,$3,'apple',$4,$5::jsonb) ON CONFLICT DO NOTHING""",
        uuid.uuid4(), owner_id, f"{kind}:{entity_id}:{operation}:{version}", operation,
        json.dumps({"entity_type": kind, "entity_id": str(entity_id), "operation": operation}),
    )
