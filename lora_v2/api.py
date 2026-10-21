"""Mini App API backed by the same commands as Telegram."""

import asyncio
import json
import os
import uuid
from contextlib import asynccontextmanager
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

import asyncpg
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from lora_v2.auth import owner_from_header
from lora_v2.academics import AcademicKind, delete_academic, list_academics, set_semester, write_academic
from lora_v2.academic_calendar import materialize_schedule
from lora_v2.apple import AppleRemote, resolve_conflict
from lora_v2.apple_events import AppleEventRemote, resolve_event_conflict
from lora_v2.config import Settings
from lora_v2.crud import EditRequest, EntityKind, delete_entity, update_entity
from lora_v2.db import create_pool, migrate
from lora_v2.models import Command, ReceiptLine
from lora_v2.media import save_photo
from lora_v2.migrate_legacy import PROFILE_FIELDS
from lora_v2.obsidian import list_schedule_conflicts, resolve_schedule_conflict
from lora_v2.proactive import decide_followup, decide_proposal, expire_stale_proposals
from lora_v2.service import capture, execute_command


class CaptureRequest(BaseModel):
    external_id: str = Field(min_length=1, max_length=200)
    text: str = Field(min_length=1)


class ActionRequest(BaseModel):
    idempotency_key: str = Field(min_length=1, max_length=200)
    command: Command


class DecisionRequest(BaseModel):
    accept: bool


class ReceiptProposalEdit(BaseModel):
    expected_version: int = Field(ge=1)
    merchant: str | None = Field(default=None, max_length=200)
    total_amount: Decimal = Field(gt=0)
    items: list[ReceiptLine] = Field(min_length=1, max_length=100)


class FollowupDecision(BaseModel):
    choice: Literal["done", "tomorrow"]


class AppleConflictDecision(BaseModel):
    choice: Literal["keep_local", "use_apple"]


class ObsidianConflictDecision(BaseModel):
    choice: Literal["keep_lora", "use_obsidian"]
    expected_version: int = Field(ge=1)
    file_revision: str = Field(min_length=64, max_length=64)


class AppleEventConflictDecision(BaseModel):
    choice: Literal['keep_lora', 'use_apple']
    expected_version: int = Field(ge=1)


class AcademicWriteRequest(BaseModel):
    data: dict[str, object]
    expected_version: int | None = None


class MoodlePostUpdate(BaseModel):
    is_read: bool | None = None
    archived: bool | None = None


class SemesterRequest(BaseModel):
    semester_start: date
    semester_end: date | None = None
    expected_version: int | None = None


class ReflectionRequest(BaseModel):
    entry_date: date
    reflection_text: str | None = None
    mood: str | None = None
    tomorrow_focus: str | None = None
    task_completion: str | None = None
    skipped: bool = False
    expected_version: int | None = None


class PlanRequest(BaseModel):
    plan_date: date
    user_input: str | None = None
    itinerary: str | None = None
    wake_time: time | None = None
    expected_version: int | None = None


class PreferencesRequest(BaseModel):
    data: dict[str, object]
    expected_version: int | None = None


class NutritionTargetsRequest(BaseModel):
    calories: int | None = Field(default=None, ge=0)
    protein_g: int | None = Field(default=None, ge=0)
    carbs_g: int | None = Field(default=None, ge=0)
    fat_g: int | None = Field(default=None, ge=0)
    expected_version: int | None = None


class ExpenseCategoryRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    icon: str | None = None
    keywords: list[str] = Field(default_factory=list)
    is_active: bool = True
    expected_version: int | None = None


class MerchantRuleRequest(BaseModel):
    merchant_key: str = Field(min_length=1, max_length=120)
    category: str = Field(min_length=1, max_length=100)
    expected_version: int | None = None


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.pool = await create_pool(config)
        await migrate(app.state.pool)
        try:
            yield
        finally:
            await app.state.pool.close()

    app = FastAPI(title="Lora v2", lifespan=lifespan)
    auth = owner_from_header(config)

    @app.get("/health")
    async def health(request: Request):
        await request.app.state.pool.fetchval("SELECT 1")
        return {"status": "ok", "runtime": "v2"}

    @app.get("/api/v2/integrations")
    async def integrations(request: Request, owner_id: int = Depends(auth)):
        rows = await request.app.state.pool.fetch("SELECT name,status,checked_at,detail FROM integration_status ORDER BY name")
        return [dict(row) for row in rows]

    @app.get('/api/v2/daily-history')
    async def daily_history(request: Request, owner_id: int = Depends(auth)):
        async with request.app.state.pool.acquire() as conn:
            reflections = await conn.fetch(
                """SELECT id,entry_date,reflection_text,mood,tomorrow_focus,task_completion,
                skipped,version FROM daily_reflections WHERE owner_id=$1 AND deleted_at IS NULL
                ORDER BY entry_date DESC LIMIT 200""", owner_id,
            )
            plans = await conn.fetch(
                """SELECT id,plan_date,user_input,itinerary,wake_time,version FROM day_plans_v2
                WHERE owner_id=$1 AND deleted_at IS NULL ORDER BY plan_date DESC LIMIT 200""", owner_id,
            )
            categories = await conn.fetch(
                """SELECT id,name,icon,keywords,is_active,version FROM expense_categories
                WHERE owner_id=$1 ORDER BY name""", owner_id,
            )
            merchant_rules = await conn.fetch(
                """SELECT merchant_key,category,version FROM expense_category_rules
                WHERE owner_id=$1 ORDER BY merchant_key LIMIT 200""", owner_id,
            )
            preferences = await conn.fetchrow(
                'SELECT data,version FROM personal_preferences WHERE owner_id=$1', owner_id,
            )
            targets = await conn.fetchrow(
                """SELECT calories,protein_g,carbs_g,fat_g,version FROM nutrition_targets_v2
                WHERE owner_id=$1""", owner_id,
            )
        return {
            'reflections': [dict(row) for row in reflections],
            'plans': [dict(row) for row in plans],
            'categories': [dict(row) for row in categories],
            'merchant_rules': [dict(row) for row in merchant_rules],
            'preferences': {'data': json.loads(preferences['data']), 'version': preferences['version']} if preferences else None,
            'nutrition_targets': dict(targets) if targets else None,
        }

    @app.post('/api/v2/daily-history/reflections')
    async def create_reflection(body: ReflectionRequest, request: Request, owner_id: int = Depends(auth)):
        try:
            row = await request.app.state.pool.fetchrow(
                """INSERT INTO daily_reflections(id,owner_id,entry_date,reflection_text,mood,
                tomorrow_focus,task_completion,skipped)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
                ON CONFLICT(owner_id,entry_date) DO UPDATE SET
                reflection_text=EXCLUDED.reflection_text,mood=EXCLUDED.mood,
                tomorrow_focus=EXCLUDED.tomorrow_focus,task_completion=EXCLUDED.task_completion,
                skipped=EXCLUDED.skipped,deleted_at=NULL,version=daily_reflections.version+1,
                updated_at=now() WHERE daily_reflections.deleted_at IS NOT NULL
                RETURNING id,version""",
                uuid.uuid4(), owner_id, body.entry_date, body.reflection_text, body.mood,
                body.tomorrow_focus, body.task_completion, body.skipped,
            )
        except asyncpg.UniqueViolationError as exc:
            raise HTTPException(status_code=409, detail='Există deja o reflecție în acea zi.') from exc
        if not row:
            raise HTTPException(status_code=409, detail='Există deja o reflecție în acea zi.')
        return dict(row)

    @app.put('/api/v2/daily-history/reflections/{entity_id}')
    async def edit_reflection(entity_id: uuid.UUID, body: ReflectionRequest, request: Request,
                              owner_id: int = Depends(auth)):
        try:
            row = await request.app.state.pool.fetchrow(
                """UPDATE daily_reflections SET entry_date=$4,reflection_text=$5,mood=$6,
                tomorrow_focus=$7,task_completion=$8,skipped=$9,version=version+1,updated_at=now()
                WHERE id=$1 AND owner_id=$2 AND version=$3 AND deleted_at IS NULL
                RETURNING id,version""",
                entity_id, owner_id, body.expected_version, body.entry_date,
                body.reflection_text, body.mood, body.tomorrow_focus, body.task_completion, body.skipped,
            )
        except asyncpg.UniqueViolationError as exc:
            raise HTTPException(status_code=409, detail='Există deja o reflecție în acea zi.') from exc
        if not row:
            raise HTTPException(status_code=409, detail='Reflecția a fost modificată între timp.')
        return dict(row)

    @app.delete('/api/v2/daily-history/reflections/{entity_id}')
    async def delete_reflection(entity_id: uuid.UUID, expected_version: int, request: Request,
                                owner_id: int = Depends(auth)):
        row = await request.app.state.pool.fetchrow(
            """UPDATE daily_reflections SET deleted_at=now(),version=version+1,updated_at=now()
            WHERE id=$1 AND owner_id=$2 AND version=$3 AND deleted_at IS NULL
            RETURNING id,version""", entity_id, owner_id, expected_version,
        )
        if not row:
            raise HTTPException(status_code=409, detail='Reflecția a fost modificată între timp.')
        return dict(row)

    @app.post('/api/v2/daily-history/plans')
    async def create_plan(body: PlanRequest, request: Request, owner_id: int = Depends(auth)):
        row = await request.app.state.pool.fetchrow(
            """INSERT INTO day_plans_v2(id,owner_id,plan_date,user_input,itinerary,wake_time)
            VALUES ($1,$2,$3,$4,$5,$6)
            ON CONFLICT(owner_id,plan_date) DO UPDATE SET
            user_input=EXCLUDED.user_input,itinerary=EXCLUDED.itinerary,
            wake_time=EXCLUDED.wake_time,deleted_at=NULL,version=day_plans_v2.version+1,
            updated_at=now() WHERE day_plans_v2.deleted_at IS NOT NULL RETURNING id,version""",
            uuid.uuid4(), owner_id, body.plan_date, body.user_input, body.itinerary, body.wake_time,
        )
        if not row:
            raise HTTPException(status_code=409, detail='Există deja un plan în acea zi.')
        return dict(row)

    @app.put('/api/v2/daily-history/plans/{entity_id}')
    async def edit_plan(entity_id: uuid.UUID, body: PlanRequest, request: Request,
                        owner_id: int = Depends(auth)):
        try:
            row = await request.app.state.pool.fetchrow(
                """UPDATE day_plans_v2 SET plan_date=$4,user_input=$5,itinerary=$6,
                wake_time=$7,version=version+1,updated_at=now()
                WHERE id=$1 AND owner_id=$2 AND version=$3 AND deleted_at IS NULL
                RETURNING id,version""",
                entity_id, owner_id, body.expected_version, body.plan_date,
                body.user_input, body.itinerary, body.wake_time,
            )
        except asyncpg.UniqueViolationError as exc:
            raise HTTPException(status_code=409, detail='Există deja un plan în acea zi.') from exc
        if not row:
            raise HTTPException(status_code=409, detail='Planul a fost modificat între timp.')
        return dict(row)

    @app.delete('/api/v2/daily-history/plans/{entity_id}')
    async def delete_plan(entity_id: uuid.UUID, expected_version: int, request: Request,
                          owner_id: int = Depends(auth)):
        row = await request.app.state.pool.fetchrow(
            """UPDATE day_plans_v2 SET deleted_at=now(),version=version+1,updated_at=now()
            WHERE id=$1 AND owner_id=$2 AND version=$3 AND deleted_at IS NULL
            RETURNING id,version""", entity_id, owner_id, expected_version,
        )
        if not row:
            raise HTTPException(status_code=409, detail='Planul a fost modificat între timp.')
        return dict(row)

    @app.put('/api/v2/daily-history/preferences')
    async def save_preferences(body: PreferencesRequest, request: Request,
                               owner_id: int = Depends(auth)):
        if set(body.data) - set(PROFILE_FIELDS):
            raise HTTPException(status_code=422, detail='Câmp de preferințe necunoscut.')
        row = await request.app.state.pool.fetchrow(
            """INSERT INTO personal_preferences(owner_id,data) VALUES ($1,$2::jsonb)
            ON CONFLICT(owner_id) DO UPDATE SET data=EXCLUDED.data,
            version=personal_preferences.version+1,updated_at=now()
            WHERE personal_preferences.version=$3 RETURNING version""",
            owner_id, json.dumps(body.data, ensure_ascii=False), body.expected_version,
        )
        if not row:
            raise HTTPException(status_code=409, detail='Preferințele au fost modificate între timp.')
        return dict(row)

    @app.put('/api/v2/daily-history/nutrition-targets')
    async def save_nutrition_targets(body: NutritionTargetsRequest, request: Request,
                                     owner_id: int = Depends(auth)):
        row = await request.app.state.pool.fetchrow(
            """INSERT INTO nutrition_targets_v2(owner_id,calories,protein_g,carbs_g,fat_g)
            VALUES ($1,$2,$3,$4,$5)
            ON CONFLICT(owner_id) DO UPDATE SET calories=EXCLUDED.calories,
            protein_g=EXCLUDED.protein_g,carbs_g=EXCLUDED.carbs_g,fat_g=EXCLUDED.fat_g,
            version=nutrition_targets_v2.version+1,updated_at=now()
            WHERE nutrition_targets_v2.version=$6 RETURNING version""",
            owner_id, body.calories, body.protein_g, body.carbs_g, body.fat_g,
            body.expected_version,
        )
        if not row:
            raise HTTPException(status_code=409, detail='Țintele au fost modificate între timp.')
        return dict(row)

    @app.post('/api/v2/daily-history/categories')
    async def create_expense_category(body: ExpenseCategoryRequest, request: Request,
                                      owner_id: int = Depends(auth)):
        try:
            row = await request.app.state.pool.fetchrow(
                """INSERT INTO expense_categories(id,owner_id,name,icon,keywords,is_active)
                VALUES ($1,$2,$3,$4,$5,$6) RETURNING id,version""",
                uuid.uuid4(), owner_id, body.name, body.icon, body.keywords, body.is_active,
            )
        except asyncpg.UniqueViolationError as exc:
            raise HTTPException(status_code=409, detail='Categoria există deja.') from exc
        return dict(row)

    @app.put('/api/v2/daily-history/categories/{entity_id}')
    async def edit_expense_category(entity_id: uuid.UUID, body: ExpenseCategoryRequest,
                                    request: Request, owner_id: int = Depends(auth)):
        try:
            row = await request.app.state.pool.fetchrow(
                """UPDATE expense_categories SET name=$4,icon=$5,keywords=$6,
                is_active=$7,version=version+1 WHERE id=$1 AND owner_id=$2 AND version=$3
                RETURNING id,version""",
                entity_id, owner_id, body.expected_version, body.name, body.icon,
                body.keywords, body.is_active,
            )
        except asyncpg.UniqueViolationError as exc:
            raise HTTPException(status_code=409, detail='Categoria există deja.') from exc
        if not row:
            raise HTTPException(status_code=409, detail='Categoria a fost modificată între timp.')
        return dict(row)

    @app.delete('/api/v2/daily-history/categories/{entity_id}')
    async def delete_expense_category(entity_id: uuid.UUID, expected_version: int,
                                      request: Request, owner_id: int = Depends(auth)):
        row = await request.app.state.pool.fetchrow(
            """UPDATE expense_categories SET is_active=false,version=version+1
            WHERE id=$1 AND owner_id=$2 AND version=$3 AND is_active=true RETURNING id,version""",
            entity_id, owner_id, expected_version,
        )
        if not row:
            raise HTTPException(status_code=409, detail='Categoria a fost modificată între timp.')
        return dict(row)

    @app.post('/api/v2/daily-history/merchant-rules')
    async def create_merchant_rule(body: MerchantRuleRequest, request: Request,
                                   owner_id: int = Depends(auth)):
        key = body.merchant_key.casefold().strip()
        category = await request.app.state.pool.fetchval(
            """SELECT name FROM expense_categories WHERE owner_id=$1 AND is_active=true
            AND lower(name)=lower($2)""", owner_id, body.category.strip(),
        )
        if not key or not category:
            raise HTTPException(status_code=422, detail='Alege un comerciant și o categorie activă.')
        try:
            row = await request.app.state.pool.fetchrow(
                """INSERT INTO expense_category_rules(owner_id,merchant_key,category)
                VALUES ($1,$2,$3) RETURNING merchant_key,category,version""",
                owner_id, key, category,
            )
        except asyncpg.UniqueViolationError as exc:
            raise HTTPException(status_code=409, detail='Există deja o regulă pentru comerciant.') from exc
        return dict(row)

    @app.put('/api/v2/daily-history/merchant-rules')
    async def edit_merchant_rule(body: MerchantRuleRequest, request: Request,
                                 owner_id: int = Depends(auth)):
        category = await request.app.state.pool.fetchval(
            """SELECT name FROM expense_categories WHERE owner_id=$1 AND is_active=true
            AND lower(name)=lower($2)""", owner_id, body.category.strip(),
        )
        if not category or body.expected_version is None:
            raise HTTPException(status_code=422, detail='Alege o categorie activă și versiunea regulii.')
        row = await request.app.state.pool.fetchrow(
            """UPDATE expense_category_rules SET category=$4,source_expense_id=NULL,
            version=version+1,updated_at=now()
            WHERE owner_id=$1 AND merchant_key=$2 AND version=$3
            RETURNING merchant_key,category,version""",
            owner_id, body.merchant_key.casefold().strip(), body.expected_version, category,
        )
        if not row:
            raise HTTPException(status_code=409, detail='Regula a fost modificată între timp.')
        return dict(row)

    @app.delete('/api/v2/daily-history/merchant-rules')
    async def delete_merchant_rule(merchant_key: str, expected_version: int, request: Request,
                                   owner_id: int = Depends(auth)):
        row = await request.app.state.pool.fetchrow(
            """DELETE FROM expense_category_rules WHERE owner_id=$1 AND merchant_key=$2
            AND version=$3 RETURNING merchant_key""",
            owner_id, merchant_key.casefold().strip(), expected_version,
        )
        if not row:
            raise HTTPException(status_code=409, detail='Regula a fost modificată între timp.')
        return dict(row)

    @app.get("/api/v2/obsidian/conflicts")
    async def obsidian_conflicts(request: Request, owner_id: int = Depends(auth)):
        vault = os.getenv('OBSIDIAN_VAULT_PATH')
        return await list_schedule_conflicts(request.app.state.pool, owner_id, Path(vault)) if vault else []

    @app.get('/api/v2/apple/event-conflicts')
    async def apple_event_conflicts(request: Request, owner_id: int = Depends(auth)):
        rows = await request.app.state.pool.fetch(
            """SELECT c.entity_id,c.apple_uid,c.local_version,e.title,e.starts_at,e.ends_at,
            e.notes,e.status FROM apple_event_conflicts c JOIN calendar_entries e
            ON e.id=c.entity_id AND e.owner_id=c.owner_id
            WHERE c.owner_id=$1 AND c.status='pending' ORDER BY c.created_at DESC""",
            owner_id,
        )
        remote = AppleEventRemote(config)
        result = []
        for row in rows:
            try:
                snapshot = await asyncio.to_thread(remote.get_snapshot, row['apple_uid'])
            except Exception:
                snapshot = {'unavailable': True}
            result.append({**dict(row), 'apple': snapshot})
        return result

    @app.post('/api/v2/apple/event-conflicts/{entity_id}/decision')
    async def apple_event_conflict_decision(
        entity_id: uuid.UUID, body: AppleEventConflictDecision, request: Request,
        owner_id: int = Depends(auth),
    ):
        try:
            message = await resolve_event_conflict(request.app.state.pool, config, owner_id,
                                                   entity_id, body.choice, body.expected_version)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {'status': 'resolved', 'message': message}

    @app.post("/api/v2/obsidian/conflicts/{entity_id}/decision")
    async def obsidian_conflict_decision(
        entity_id: uuid.UUID, body: ObsidianConflictDecision, request: Request,
        owner_id: int = Depends(auth),
    ):
        vault = os.getenv('OBSIDIAN_VAULT_PATH')
        if not vault:
            raise HTTPException(status_code=503, detail='Obsidian nu este configurat.')
        try:
            await resolve_schedule_conflict(
                request.app.state.pool, owner_id, Path(vault), entity_id,
                body.choice, body.expected_version, body.file_revision,
            )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {'status': 'resolved', 'message': 'Alegerea pentru orar a fost salvată.'}

    @app.post("/api/v2/captures")
    async def create_capture(body: CaptureRequest, request: Request, owner_id: int = Depends(auth)):
        row = await capture(request.app.state.pool, owner_id, "mini_app", body.external_id, body.text)
        return {"id": str(row["id"]), "status": row["status"]}

    @app.post("/api/v2/captures/photo")
    async def create_photo_capture(request: Request, caption: str = "", owner_id: int = Depends(auth)):
        if int(request.headers.get("content-length", "0") or "0") > 10 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="Fotografia este prea mare")
        data = await request.body()
        try:
            reference = save_photo(config, data)
        except (ValueError, OSError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        row = await capture(
            request.app.state.pool, owner_id, "mini_app_photo", str(uuid.uuid4()),
            caption[:1000], content_type="photo", attachment_ref=reference,
        )
        return {"id": str(row["id"]), "status": row["status"]}

    @app.get("/api/v2/captures/{capture_id}")
    async def get_capture(capture_id: uuid.UUID, request: Request, owner_id: int = Depends(auth)):
        async with request.app.state.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id,status,error_code,created_at,processed_at FROM captures WHERE id=$1 AND owner_id=$2",
                capture_id, owner_id,
            )
            if not row:
                raise HTTPException(status_code=404, detail="Capture not found")
            receipt = await conn.fetchval(
                """SELECT payload->>'text' FROM notification_outbox
                WHERE owner_id=$1 AND dedupe_key=$2""",
                owner_id, f"capture_receipt:{capture_id}:result",
            )
            if receipt is None:
                receipt = await conn.fetchval(
                    """SELECT payload->>'text' FROM notification_outbox
                    WHERE owner_id=$1 AND dedupe_key=$2""",
                    owner_id, f"capture_receipt:{capture_id}:retry",
                )
        return {**dict(row), "receipt": receipt}

    @app.post("/api/v2/actions")
    async def run_action(body: ActionRequest, request: Request, owner_id: int = Depends(auth)):
        try:
            return await execute_command(
                request.app.state.pool, config, owner_id, body.command, body.idempotency_key
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/api/v2/proposals/{proposal_id}/decision")
    async def proposal_decision(proposal_id: uuid.UUID, body: DecisionRequest, request: Request, owner_id: int = Depends(auth)):
        result = await decide_proposal(request.app.state.pool, config, owner_id, proposal_id, body.accept)
        return result or {"status": "rejected_or_unavailable"}

    @app.put("/api/v2/proposals/{proposal_id}/receipt")
    async def edit_receipt_proposal(proposal_id: uuid.UUID, body: ReceiptProposalEdit,
                                    request: Request, owner_id: int = Depends(auth)):
        async with request.app.state.pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    """SELECT command,version FROM proposals WHERE id=$1 AND owner_id=$2
                    AND status='pending' AND expires_at>now() FOR UPDATE""",
                    proposal_id, owner_id,
                )
                if not row or row["version"] != body.expected_version:
                    raise HTTPException(status_code=409, detail="Bonul a fost modificat. Reîncarcă propunerea.")
                previous = Command.model_validate(json.loads(row["command"]))
                if previous.type != "log_receipt":
                    raise HTTPException(status_code=422, detail="Aceasta nu este o propunere de bon.")
                data = dict(previous.data)
                data.update(merchant=body.merchant, total_amount=str(body.total_amount),
                            items=[item.model_copy(update={"category_uncertain": False}).model_dump(mode="json")
                                   for item in body.items])
                command = Command(type="log_receipt", data=data)
                try:
                    command.payload()
                except ValueError as exc:
                    raise HTTPException(status_code=422, detail="Totalul trebuie să fie egal cu suma produselor.") from exc
                reason = "Verifică bonul corectat înainte de salvare:\n" + "\n".join(
                    f"• {item.name}: {item.amount} RON · {item.category}" for item in body.items
                ) + f"\nTotal: {body.total_amount} RON"
                version = await conn.fetchval(
                    """UPDATE proposals SET command=$3::jsonb,reason=$4,version=version+1
                    WHERE id=$1 AND owner_id=$2 RETURNING version""",
                    proposal_id, owner_id, json.dumps(command.model_dump(mode="json")), reason,
                )
        return {"id": str(proposal_id), "version": version, "reason": reason}

    @app.post("/api/v2/proposals/{proposal_id}/followup")
    async def followup_decision(proposal_id: uuid.UUID, body: FollowupDecision,
                                request: Request, owner_id: int = Depends(auth)):
        result = await decide_followup(
            request.app.state.pool, config, owner_id, proposal_id, body.choice,
        )
        if result is None:
            raise HTTPException(status_code=409, detail="Întrebarea nu mai este disponibilă")
        return result

    @app.get("/api/v2/proposals")
    async def proposals(request: Request, owner_id: int = Depends(auth)):
        async with request.app.state.pool.acquire() as conn:
            await expire_stale_proposals(conn, owner_id)
            rows = await conn.fetch(
                """SELECT id,source,reason,command,expires_at,version FROM proposals
                WHERE owner_id=$1 AND status='pending' AND expires_at > now()
                ORDER BY created_at DESC LIMIT 20""",
                owner_id,
            )
        return [dict(row) for row in rows]

    @app.get("/api/v2/apple/conflicts")
    async def apple_conflicts(request: Request, owner_id: int = Depends(auth)):
        async with request.app.state.pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT c.id,c.entity_type,c.entity_id,c.apple_uid,c.local_version,
                c.apple_revision,c.created_at,COALESCE(t.title,e.title) AS local_title
                FROM apple_sync_conflicts c
                LEFT JOIN tasks t ON c.entity_type='task' AND t.id=c.entity_id
                LEFT JOIN calendar_entries e ON c.entity_type='calendar_entry' AND e.id=c.entity_id
                WHERE c.owner_id=$1 AND c.status='pending'
                ORDER BY c.created_at DESC LIMIT 20""",
                owner_id,
            )
        return [dict(row) for row in rows]

    @app.post("/api/v2/apple/conflicts/{conflict_id}/decision")
    async def apple_conflict_decision(
        conflict_id: uuid.UUID, body: AppleConflictDecision, request: Request,
        owner_id: int = Depends(auth),
    ):
        try:
            message = await resolve_conflict(
                request.app.state.pool, config, owner_id, conflict_id, body.choice,
            )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {"status": "resolved", "message": message}

    @app.get("/api/v2/apple/conflicts/{conflict_id}")
    async def apple_conflict_detail(
        conflict_id: uuid.UUID, request: Request, owner_id: int = Depends(auth),
    ):
        async with request.app.state.pool.acquire() as conn:
            conflict = await conn.fetchrow(
                """SELECT entity_type,entity_id,apple_uid,status FROM apple_sync_conflicts
                WHERE id=$1 AND owner_id=$2""",
                conflict_id, owner_id,
            )
            if not conflict or conflict["status"] != "pending":
                raise HTTPException(status_code=404, detail="Conflictul nu mai este disponibil")
            if conflict["entity_type"] == "task":
                local = await conn.fetchrow(
                    "SELECT title,due_at AS at,status,version FROM tasks WHERE id=$1 AND owner_id=$2",
                    conflict["entity_id"], owner_id,
                )
            else:
                local = await conn.fetchrow(
                    "SELECT title,starts_at AS at,status,version FROM calendar_entries WHERE id=$1 AND owner_id=$2",
                    conflict["entity_id"], owner_id,
                )
        snapshots = await asyncio.to_thread(AppleRemote(config).list_all)
        remote = next((item for item in snapshots if item[0] == conflict["apple_uid"]), None)
        return {
            "local": dict(local) if local else None,
            "apple": {"title": remote[2], "at": remote[3], "completed": remote[4]} if remote else None,
            "apple_deleted": remote is None,
        }

    @app.get("/api/v2/today")
    async def today(request: Request, owner_id: int = Depends(auth)):
        now = datetime.now(ZoneInfo(config.timezone))
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        async with request.app.state.pool.acquire() as conn:
            entries = await conn.fetch(
                """SELECT id,kind,title,starts_at,ends_at,status,version FROM calendar_entries
                WHERE owner_id=$1 AND starts_at >= $2 AND starts_at < $3 AND status='active'
                ORDER BY starts_at""",
                owner_id, start, end,
            )
            tasks = await conn.fetch(
                """SELECT t.id,t.title,t.due_at,t.status,t.version,p.name AS project_name
                FROM tasks t LEFT JOIN projects p ON p.id=t.project_id
                WHERE t.owner_id=$1 AND t.status='pending' AND (t.due_at < $2 OR t.due_at IS NULL)
                ORDER BY t.due_at NULLS LAST,t.created_at LIMIT 20""",
                owner_id, end,
            )
        return {"date": start.date().isoformat(), "entries": [dict(row) for row in entries], "tasks": [dict(row) for row in tasks]}

    @app.get("/api/v2/university")
    async def university(request: Request, owner_id: int = Depends(auth)):
        return await list_academics(request.app.state.pool, owner_id)

    @app.get("/api/v2/moodle")
    async def moodle_library(request: Request, owner_id: int = Depends(auth)):
        async with request.app.state.pool.acquire() as conn:
            courses = await conn.fetch(
                """SELECT course_url,course_title,folder_name,material_count,last_synced_at
                FROM moodle_course_sync WHERE owner_id=$1 ORDER BY course_title""", owner_id,
            )
            materials = await conn.fetch(
                """SELECT id,course_url,title,section_title,filename,relative_path,sha256
                FROM moodle_materials WHERE owner_id=$1 ORDER BY course_url,section_title,filename""", owner_id,
            )
            posts = await conn.fetch(
                """SELECT id,course_url,course_title,forum_title,kind,discussion_url,title,
                body,is_read,first_seen_at,updated_at FROM moodle_posts
                WHERE owner_id=$1 AND archived_at IS NULL ORDER BY updated_at DESC LIMIT 200""", owner_id,
            )
        return {"courses": [dict(row) for row in courses],
                "materials": [dict(row) for row in materials],
                "posts": [dict(row) for row in posts]}

    @app.put("/api/v2/moodle/posts/{post_id}")
    async def update_moodle_post(post_id: uuid.UUID, body: MoodlePostUpdate,
                                 request: Request, owner_id: int = Depends(auth)):
        if body.is_read is None and body.archived is None:
            raise HTTPException(status_code=422, detail="Alege o modificare.")
        result = await request.app.state.pool.fetchrow(
            """UPDATE moodle_posts SET is_read=COALESCE($3,is_read),
            archived_at=CASE WHEN $4::boolean IS NULL THEN archived_at
            WHEN $4 THEN now() ELSE NULL END WHERE id=$1 AND owner_id=$2
            RETURNING id,is_read,archived_at""",
            post_id, owner_id, body.is_read, body.archived,
        )
        if result is None:
            raise HTTPException(status_code=404, detail="Mesajul nu mai este disponibil.")
        return dict(result)

    @app.get("/api/v2/university/week")
    async def university_week(week_start: date, request: Request, owner_id: int = Depends(auth)):
        monday = week_start - timedelta(days=week_start.weekday())
        await materialize_schedule(request.app.state.pool, config, owner_id, start=monday, days=7)
        start = datetime.combine(monday, datetime.min.time(), ZoneInfo(config.timezone))
        end = start + timedelta(days=7)
        async with request.app.state.pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT id,kind,title,starts_at,ends_at,notes,status,version
                FROM calendar_entries WHERE owner_id=$1 AND kind='academic' AND status='active'
                AND starts_at >= $2 AND starts_at < $3 ORDER BY starts_at""",
                owner_id, start, end,
            )
        return [dict(row) for row in rows]

    @app.put("/api/v2/university/semester")
    async def university_semester(body: SemesterRequest, request: Request, owner_id: int = Depends(auth)):
        try:
            result = await set_semester(
                request.app.state.pool, owner_id, body.semester_start,
                body.semester_end, body.expected_version,
            )
            await materialize_schedule(request.app.state.pool, config, owner_id, days=60)
            return result
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/api/v2/university/{kind}")
    async def add_university_item(kind: AcademicKind, body: AcademicWriteRequest,
                                  request: Request, owner_id: int = Depends(auth)):
        try:
            result = await write_academic(request.app.state.pool, owner_id, kind, body.data)
            if kind in {"subject", "schedule", "exam", "vacation"}:
                await materialize_schedule(request.app.state.pool, config, owner_id, days=60)
            return result
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.put("/api/v2/university/{kind}/{entity_id}")
    async def edit_university_item(kind: AcademicKind, entity_id: uuid.UUID,
                                   body: AcademicWriteRequest, request: Request,
                                   owner_id: int = Depends(auth)):
        try:
            result = await write_academic(
                request.app.state.pool, owner_id, kind, body.data,
                entity_id, body.expected_version,
            )
            if kind in {"subject", "schedule", "exam", "vacation"}:
                await materialize_schedule(request.app.state.pool, config, owner_id, days=60)
            return result
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.delete("/api/v2/university/{kind}/{entity_id}")
    async def remove_university_item(kind: AcademicKind, entity_id: uuid.UUID,
                                     expected_version: int, request: Request,
                                     owner_id: int = Depends(auth)):
        try:
            result = await delete_academic(
                request.app.state.pool, owner_id, kind, entity_id, expected_version,
            )
            if kind in {"subject", "schedule", "exam", "vacation"}:
                await materialize_schedule(request.app.state.pool, config, owner_id, days=60)
            return result
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/api/v2/calendar")
    async def calendar(request: Request, from_at: datetime, to_at: datetime, owner_id: int = Depends(auth)):
        if from_at.tzinfo is None or to_at.tzinfo is None or to_at <= from_at or to_at - from_at > timedelta(days=62):
            raise HTTPException(status_code=422, detail="Use an interval of up to 62 days with timezone")
        async with request.app.state.pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT id,kind,title,starts_at,ends_at,notes,status,version FROM calendar_entries
                WHERE owner_id=$1 AND starts_at >= $2 AND starts_at < $3 AND status!='cancelled'
                ORDER BY starts_at""",
                owner_id, from_at, to_at,
            )
        return [dict(row) for row in rows]

    @app.get("/api/v2/projects")
    async def projects(request: Request, owner_id: int = Depends(auth)):
        async with request.app.state.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id,name,status,version FROM projects WHERE owner_id=$1 ORDER BY name", owner_id
            )
        return [dict(row) for row in rows]

    @app.get("/api/v2/tasks")
    async def tasks(request: Request, owner_id: int = Depends(auth)):
        async with request.app.state.pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT t.id,t.title,t.notes,t.due_at,t.status,t.project_id,t.version,p.name AS project_name
                FROM tasks t LEFT JOIN projects p ON p.id=t.project_id
                WHERE t.owner_id=$1 ORDER BY t.status,t.due_at NULLS LAST,t.created_at DESC LIMIT 500""",
                owner_id,
            )
        return [dict(row) for row in rows]

    @app.get("/api/v2/journal")
    async def journal(request: Request, owner_id: int = Depends(auth)):
        async with request.app.state.pool.acquire() as conn:
            expenses = await conn.fetch(
                "SELECT id,amount,currency,category,merchant,description,spent_at,version FROM expenses WHERE owner_id=$1 AND deleted_at IS NULL ORDER BY spent_at DESC LIMIT 100", owner_id
            )
            incomes = await conn.fetch(
                """SELECT id,amount,currency,category,source,description,received_at,version
                FROM incomes WHERE owner_id=$1 AND deleted_at IS NULL ORDER BY received_at DESC LIMIT 100""",
                owner_id,
            )
            meals = await conn.fetch(
                """SELECT m.id,m.eaten_at,m.description,m.estimate_uncertain,m.version,
                CASE WHEN COUNT(i.id)>0 AND COUNT(i.id)=COUNT(i.calories)
                    AND COUNT(i.id)=COUNT(i.protein_g) AND COUNT(i.id)=COUNT(i.carbs_g)
                    AND COUNT(i.id)=COUNT(i.fat_g) THEN ROUND(SUM(i.calories),1) END AS calories,
                CASE WHEN COUNT(i.id)>0 AND COUNT(i.id)=COUNT(i.protein_g)
                    THEN ROUND(SUM(i.protein_g),1) END AS protein_g,
                CASE WHEN COUNT(i.id)>0 AND COUNT(i.id)=COUNT(i.carbs_g)
                    THEN ROUND(SUM(i.carbs_g),1) END AS carbs_g,
                CASE WHEN COUNT(i.id)>0 AND COUNT(i.id)=COUNT(i.fat_g)
                    THEN ROUND(SUM(i.fat_g),1) END AS fat_g
                FROM meals m LEFT JOIN meal_items i ON i.meal_id=m.id
                WHERE m.owner_id=$1 AND m.deleted_at IS NULL GROUP BY m.id
                ORDER BY m.eaten_at DESC LIMIT 100""", owner_id
            )
            workouts = await conn.fetch(
                "SELECT id,started_at,duration_minutes,activity,notes,version FROM workouts WHERE owner_id=$1 AND deleted_at IS NULL ORDER BY started_at DESC LIMIT 100", owner_id
            )
            health = await conn.fetch(
                """SELECT id,log_date,sleep_hours,sleep_quality,water_ml,weight_kg,cigarettes,notes,version
                FROM health_entries WHERE owner_id=$1 AND deleted_at IS NULL ORDER BY log_date DESC LIMIT 100""",
                owner_id,
            )
        return {"expenses": [dict(row) for row in expenses], "incomes": [dict(row) for row in incomes],
                "meals": [dict(row) for row in meals],
                "workouts": [dict(row) for row in workouts], "health": [dict(row) for row in health]}

    @app.get("/api/v2/entities/{kind}/{entity_id}")
    async def get_entity(kind: EntityKind, entity_id: uuid.UUID, request: Request, owner_id: int = Depends(auth)):
        queries = {
            "project": "SELECT id,name,status,version FROM projects WHERE id=$1 AND owner_id=$2",
            "task": "SELECT id,title,notes,due_at,project_id,status,version FROM tasks WHERE id=$1 AND owner_id=$2",
            "calendar_entry": "SELECT id,kind,title,starts_at,ends_at,notes,followup_at,status,version FROM calendar_entries WHERE id=$1 AND owner_id=$2",
            "expense": "SELECT id,amount,currency,category,merchant,description,spent_at,version FROM expenses WHERE id=$1 AND owner_id=$2 AND deleted_at IS NULL",
            "income": "SELECT id,amount,currency,category,source,description,received_at,version FROM incomes WHERE id=$1 AND owner_id=$2 AND deleted_at IS NULL",
            "meal": "SELECT id,eaten_at,description,estimate_source,estimate_uncertain,photo_ref,version FROM meals WHERE id=$1 AND owner_id=$2 AND deleted_at IS NULL",
            "workout": "SELECT id,started_at,duration_minutes,activity,notes,version FROM workouts WHERE id=$1 AND owner_id=$2 AND deleted_at IS NULL",
            "health": "SELECT id,log_date,sleep_hours,sleep_quality,water_ml,weight_kg,cigarettes,notes,version FROM health_entries WHERE id=$1 AND owner_id=$2 AND deleted_at IS NULL",
        }
        async with request.app.state.pool.acquire() as conn:
            row = await conn.fetchrow(queries[kind], entity_id, owner_id)
            if not row:
                raise HTTPException(status_code=404, detail="Elementul nu există")
            result = dict(row)
            if kind == "meal":
                items = await conn.fetch(
                    """SELECT id,name,grams,calories,protein_g,carbs_g,fat_g,nutrition_provider,
                    nutrition_source_id,nutrition_source_title,nutrition_source_url
                    FROM meal_items WHERE meal_id=$1 ORDER BY id""",
                    entity_id,
                )
                result["items"] = [dict(item) for item in items]
            if kind == "workout":
                exercises = await conn.fetch(
                    "SELECT id,name,sets,reps,weight_kg FROM workout_exercises WHERE workout_id=$1 ORDER BY id",
                    entity_id,
                )
                result["exercises"] = [dict(exercise) for exercise in exercises]
            if kind == "calendar_entry":
                alerts = await conn.fetch(
                    "SELECT purpose FROM alert_occurrences WHERE entry_id=$1 AND status!='cancelled'",
                    entity_id,
                )
                result["alert_offsets_minutes"] = sorted({
                    int(item["purpose"].removeprefix("before_").removesuffix("m"))
                    for item in alerts if item["purpose"].startswith("before_")
                }, reverse=True)
        return result

    @app.put("/api/v2/entities/{kind}/{entity_id}")
    async def edit_entity(kind: EntityKind, entity_id: uuid.UUID, body: EditRequest, request: Request, owner_id: int = Depends(auth)):
        try:
            return await update_entity(request.app.state.pool, config, owner_id, kind, entity_id, body)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.delete("/api/v2/entities/{kind}/{entity_id}")
    async def remove_entity(kind: EntityKind, entity_id: uuid.UUID, expected_version: int, request: Request, owner_id: int = Depends(auth)):
        try:
            return await delete_entity(request.app.state.pool, owner_id, kind, entity_id, expected_version)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    dist = Path(__file__).resolve().parent / "web" / "dist"
    if (dist / "index.html").is_file():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        async def mini_app(path: str):
            if path.startswith("api/") or "." in Path(path).name:
                raise HTTPException(status_code=404)
            return FileResponse(dist / "index.html")

    return app


