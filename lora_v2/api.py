"""Mini App API backed by the same commands as Telegram."""

import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from lora_v2.auth import owner_from_header
from lora_v2.config import Settings
from lora_v2.crud import EditRequest, EntityKind, delete_entity, update_entity
from lora_v2.db import create_pool, migrate
from lora_v2.models import Command
from lora_v2.media import save_photo
from lora_v2.proactive import decide_proposal
from lora_v2.service import capture, execute_command


class CaptureRequest(BaseModel):
    external_id: str = Field(min_length=1, max_length=200)
    text: str = Field(min_length=1)


class ActionRequest(BaseModel):
    idempotency_key: str = Field(min_length=1, max_length=200)
    command: Command


class DecisionRequest(BaseModel):
    accept: bool


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
        return dict(row)

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

    @app.get("/api/v2/proposals")
    async def proposals(request: Request, owner_id: int = Depends(auth)):
        async with request.app.state.pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT id,reason,command,expires_at FROM proposals
                WHERE owner_id=$1 AND status='pending' AND expires_at > now()
                ORDER BY created_at DESC LIMIT 20""",
                owner_id,
            )
        return [dict(row) for row in rows]

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
            meals = await conn.fetch(
                "SELECT id,eaten_at,description,estimate_uncertain,version FROM meals WHERE owner_id=$1 AND deleted_at IS NULL ORDER BY eaten_at DESC LIMIT 100", owner_id
            )
            workouts = await conn.fetch(
                "SELECT id,started_at,duration_minutes,activity,notes,version FROM workouts WHERE owner_id=$1 AND deleted_at IS NULL ORDER BY started_at DESC LIMIT 100", owner_id
            )
        return {"expenses": [dict(row) for row in expenses], "meals": [dict(row) for row in meals], "workouts": [dict(row) for row in workouts]}

    @app.get("/api/v2/entities/{kind}/{entity_id}")
    async def get_entity(kind: EntityKind, entity_id: uuid.UUID, request: Request, owner_id: int = Depends(auth)):
        queries = {
            "project": "SELECT id,name,status,version FROM projects WHERE id=$1 AND owner_id=$2",
            "task": "SELECT id,title,notes,due_at,project_id,status,version FROM tasks WHERE id=$1 AND owner_id=$2",
            "calendar_entry": "SELECT id,kind,title,starts_at,ends_at,notes,followup_at,status,version FROM calendar_entries WHERE id=$1 AND owner_id=$2",
            "expense": "SELECT id,amount,currency,category,merchant,description,spent_at,version FROM expenses WHERE id=$1 AND owner_id=$2 AND deleted_at IS NULL",
            "meal": "SELECT id,eaten_at,description,estimate_source,estimate_uncertain,photo_ref,version FROM meals WHERE id=$1 AND owner_id=$2 AND deleted_at IS NULL",
            "workout": "SELECT id,started_at,duration_minutes,activity,notes,version FROM workouts WHERE id=$1 AND owner_id=$2 AND deleted_at IS NULL",
        }
        async with request.app.state.pool.acquire() as conn:
            row = await conn.fetchrow(queries[kind], entity_id, owner_id)
            if not row:
                raise HTTPException(status_code=404, detail="Elementul nu există")
            result = dict(row)
            if kind == "meal":
                items = await conn.fetch(
                    "SELECT id,name,grams,calories,protein_g,carbs_g,fat_g FROM meal_items WHERE meal_id=$1 ORDER BY id",
                    entity_id,
                )
                result["items"] = [dict(item) for item in items]
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


