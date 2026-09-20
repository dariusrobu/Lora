import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Depends, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
import asyncio
import json
from typing import List

from lora_api.config import ALLOWED_ORIGINS, DATABASE_URL, JWT_SECRET, LORA_API_PASSWORD, API_PORT
from lora_api.database import init_pool, close_pool, get_pool
from lora_api.auth import decode_token, hash_password, verify_password, create_token, get_current_user
from lora_api.routers import (
    tasks, projects, finance, university, shopping, health,
    workout, skills, reading, nutrition, goals, mood,
    memory, notes, calendar, travel, focus, weather,
    insights, location, profile, homeserver, space, llm,
    widget, news,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("lora_api")

BASE_DIR = Path(__file__).parent.parent
DIST_DIR = BASE_DIR / "dashboard" / "dist"
SCHEMA_SQL = BASE_DIR / "db" / "schema.sql"


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is required")
    if not JWT_SECRET:
        raise RuntimeError("JWT_SECRET is required")
    if not LORA_API_PASSWORD:
        raise RuntimeError("LORA_API_PASSWORD is required")
    await init_pool(DATABASE_URL)
    await _ensure_schema()
    from db.connection import apply_migrations
    await apply_migrations(await get_pool())
    await _ensure_user_table()
    logger.info(f"API server starting on port {API_PORT}")
    yield
    await close_pool()


app = FastAPI(
    title="Lora API",
    version="1.0.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# WebSocket Connection Manager — Real-time push events to dashboard
# ---------------------------------------------------------------------------

class ConnectionManager:
    """Manages active WebSocket connections for real-time dashboard updates."""

    def __init__(self):
        self._connections: List[WebSocket] = []
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket, subprotocol: str | None = None) -> None:
        await ws.accept(subprotocol=subprotocol)
        async with self._lock:
            self._connections.append(ws)
        logger.info(f"WS client connected. Total: {len(self._connections)}")

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            try:
                self._connections.remove(ws)
            except ValueError:
                pass
        logger.info(f"WS client disconnected. Total: {len(self._connections)}")

    async def broadcast(self, event_type: str, payload: dict) -> None:
        """Broadcasts a JSON event to all connected dashboard clients."""
        message = json.dumps({"type": event_type, "payload": payload})
        dead: List[WebSocket] = []
        for ws in list(self._connections):
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            await self.disconnect(ws)


# Singleton manager — imported by core/dispatcher.py for push notifications
ws_manager = ConnectionManager()

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def _ensure_schema():
    """Creates all DB tables + seed data. Idempotent — safe to re-run."""
    pool = await get_pool()

    # 1. Execute schema.sql — asyncpg handles multi-statement SQL directly
    if SCHEMA_SQL.exists():
        raw = SCHEMA_SQL.read_text(encoding="utf-8")
        async with pool.acquire() as conn:
            try:
                # Multiple processes can start during a deploy/restart.  Serialize
                # schema creation so two sessions cannot race on the same index.
                await conn.execute("SELECT pg_advisory_lock(hashtext('lora_schema'))")
                await conn.execute(raw)
                logger.info("Executed schema.sql successfully")
            except Exception as e:
                logger.warning(f"schema.sql warning (tables/indexes may already exist): {e}")
            finally:
                await conn.execute("SELECT pg_advisory_unlock(hashtext('lora_schema'))")
    else:
        logger.warning(f"schema.sql not found at {SCHEMA_SQL}")

    # 2. Additional DDL (columns not in schema.sql)
    async with pool.acquire() as conn:
        for ddl in [
            "ALTER TABLE health_logs ADD COLUMN IF NOT EXISTS cigarettes INT DEFAULT 0",
            "ALTER TABLE user_profile ADD COLUMN IF NOT EXISTS llm_provider TEXT DEFAULT 'ollama'",
            "ALTER TABLE user_profile ADD COLUMN IF NOT EXISTS llm_host TEXT DEFAULT 'http://localhost:11434'",
            "ALTER TABLE user_profile ADD COLUMN IF NOT EXISTS llm_model TEXT DEFAULT 'llama3.2:3b'",
            "CREATE TABLE IF NOT EXISTS job_config (job_name TEXT PRIMARY KEY, enabled BOOLEAN DEFAULT TRUE, cron_time TEXT, last_run TIMESTAMPTZ, last_duration_ms INT, last_error TEXT, created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW())",
            "CREATE TABLE IF NOT EXISTS backup_config (id SERIAL PRIMARY KEY, enabled BOOLEAN DEFAULT FALSE, schedule_cron TEXT DEFAULT '0 4 * * 0', retention_days INTEGER DEFAULT 30, last_backup_at TIMESTAMPTZ, next_backup_at TIMESTAMPTZ, created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW())",
            "CREATE TABLE IF NOT EXISTS backup_log (id SERIAL PRIMARY KEY, status TEXT NOT NULL DEFAULT 'pending', file_name TEXT, file_size_bytes BIGINT, error_message TEXT, started_at TIMESTAMPTZ DEFAULT NOW(), completed_at TIMESTAMPTZ, created_at TIMESTAMPTZ DEFAULT NOW())",
            "INSERT INTO backup_config (enabled, schedule_cron, retention_days) SELECT FALSE, '0 4 * * 0', 30 WHERE NOT EXISTS (SELECT 1 FROM backup_config LIMIT 1)",
            "ALTER TABLE user_profile ADD COLUMN IF NOT EXISTS units TEXT DEFAULT 'metric'",
            "ALTER TABLE user_profile ADD COLUMN IF NOT EXISTS language TEXT DEFAULT 'ro'",
            "ALTER TABLE user_profile ADD COLUMN IF NOT EXISTS week_start_day TEXT DEFAULT 'monday'",
            "ALTER TABLE user_profile ADD COLUMN IF NOT EXISTS currency TEXT DEFAULT 'RON'",
            "ALTER TABLE user_profile ADD COLUMN IF NOT EXISTS dietary_preferences TEXT",
            "ALTER TABLE user_profile ADD COLUMN IF NOT EXISTS notification_config JSONB DEFAULT '{}'",
        ]:
            try:
                await conn.execute(ddl)
            except Exception as e:
                raise RuntimeError(f"Database schema update failed: {ddl}") from e

        # 3. Seed user_profile row for the default user
        from lora_api.config import TELEGRAM_USER_ID, TIMEZONE
        morning_time = os.getenv("MORNING_BRIEFING_TIME", "08:00")
        eod_time = os.getenv("EOD_REFLECTION_TIME", "21:00")
        await conn.execute("""
            INSERT INTO user_profile (telegram_id, timezone, morning_time, eod_time, is_at_home)
            VALUES ($1, $2, $3, $4, TRUE)
            ON CONFLICT (telegram_id) DO NOTHING
        """, TELEGRAM_USER_ID, TIMEZONE, morning_time, eod_time)
        logger.info(f"Ensured user_profile row for telegram_id={TELEGRAM_USER_ID}")


async def _ensure_user_table():
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS api_users (
                id SERIAL PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        if LORA_API_PASSWORD:
            from lora_api.config import TELEGRAM_USER_ID
            email = f"user{TELEGRAM_USER_ID}@lora.local"
            existing = await conn.fetchrow("SELECT id FROM api_users WHERE email = $1", email)
            if not existing:
                await conn.execute(
                    "INSERT INTO api_users (email, password_hash) VALUES ($1, $2)",
                    email, hash_password(LORA_API_PASSWORD),
                )
                logger.info(f"Created default user {email}")


class LoginRequest(BaseModel):
    email: str
    password: str


@app.post("/api/auth/login")
async def login(body: LoginRequest):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT id, password_hash FROM api_users WHERE email = $1", body.email)
    if not row or not verify_password(body.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_token(row["id"])
    return {"access_token": token, "token_type": "bearer"}


class TelegramAuthRequest(BaseModel):
    init_data: str


@app.post("/api/auth/telegram")
async def telegram_auth(body: TelegramAuthRequest):
    """Authenticates a Telegram Mini App user via initData validation."""
    from lora_api.config import TELEGRAM_USER_ID
    from core.config import TELEGRAM_BOT_TOKEN
    import hmac
    import hashlib
    from urllib.parse import parse_qsl, unquote
    import json

    if not body.init_data:
        raise HTTPException(status_code=400, detail="Missing init_data")

    try:
        parsed = dict(parse_qsl(body.init_data, keep_blank_values=True))
        received_hash = parsed.pop("hash", None)
        if not received_hash:
            raise HTTPException(status_code=400, detail="Invalid init_data: missing hash")

        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
        secret_key = hmac.new(b"WebAppData", TELEGRAM_BOT_TOKEN.encode(), hashlib.sha256).digest()
        calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

        if not hmac.compare_digest(calculated_hash, received_hash):
            raise HTTPException(status_code=401, detail="Telegram initData hash mismatch")

        user_data = json.loads(unquote(parsed.get("user", "{}")))
        user_id = user_data.get("id")
        if not user_id or str(user_id) != str(TELEGRAM_USER_ID):
            raise HTTPException(status_code=403, detail="Unauthorized Telegram user")

        token = create_token(user_id)
        return {"access_token": token, "token_type": "bearer"}
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"Telegram auth failed: {e}")
        raise HTTPException(status_code=401, detail="Authentication failed")



@app.get("/api/health")
async def health_status():
    pool = await get_pool()
    db_ok = False
    try:
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
            db_ok = True
    except Exception:
        pass
    return {"status": "ok", "database": db_ok}


@app.get("/api/debug")
async def debug(user=Depends(get_current_user)):
    return {
        "dist_exists": DIST_DIR.exists(),
        "dist_index": (DIST_DIR / "index.html").exists() if DIST_DIR.exists() else False,
    }


@app.get("/ping")
async def ping():
    return {"status": "ok", "message": "pong"}


@app.post("/api/client-error")
async def log_client_error(data: dict, user=Depends(get_current_user)):
    err = data.get("error", "Unknown error")
    stack = data.get("stack", "")
    ua = data.get("userAgent", "")
    print(f"🚨 CLIENT ERROR [{ua}]:\n{err}\n{stack}", flush=True)
    return {"status": "logged"}


@app.websocket("/ws/live")
async def websocket_live(ws: WebSocket):
    """
    Real-time event stream for the dashboard.
    Receives push notifications when bot executes intents (tasks added, finance logged, etc.).
    Sends a heartbeat ping every 30s to keep the connection alive through proxies.

    Event format: {"type": "intent_executed", "payload": {"module": "...", "intent": "...", ...}}
    """
    protocols = [
        value.strip() for value in ws.headers.get("sec-websocket-protocol", "").split(",")
    ]
    if len(protocols) != 2 or protocols[0] != "lora-auth":
        await ws.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    try:
        decode_token(protocols[1])
    except HTTPException:
        await ws.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await ws_manager.connect(ws, subprotocol="lora-auth")
    try:
        while True:
            # Keep connection alive — send heartbeat every 30s.
            # Actual data arrives via ws_manager.broadcast() from core/dispatcher.py
            try:
                await asyncio.wait_for(ws.receive_text(), timeout=30.0)
            except asyncio.TimeoutError:
                await ws.send_text(json.dumps({"type": "heartbeat"}))
    except WebSocketDisconnect:
        pass
    finally:
        await ws_manager.disconnect(ws)


app.include_router(tasks.router)
app.include_router(projects.router)
app.include_router(finance.router)
app.include_router(university.router)
app.include_router(shopping.router)
app.include_router(health.router)
app.include_router(workout.router)
app.include_router(skills.router)
app.include_router(reading.router)
app.include_router(nutrition.router)
app.include_router(goals.router)
app.include_router(mood.router)
app.include_router(memory.router)
app.include_router(notes.router)
app.include_router(calendar.router)
app.include_router(travel.router)
app.include_router(focus.router)
app.include_router(weather.router)
app.include_router(insights.router)
app.include_router(location.router)
app.include_router(profile.router)
app.include_router(homeserver.router)
app.include_router(space.router)
app.include_router(llm.router)
app.include_router(widget.router)
app.include_router(news.router)


if DIST_DIR.exists():
    class CachedStaticFiles(StaticFiles):
        async def get_response(self, path, scope):
            from starlette.responses import FileResponse as StarletteFileResponse
            resp = await super().get_response(path, scope)
            if isinstance(resp, StarletteFileResponse):
                resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
            return resp
    app.mount("/assets", CachedStaticFiles(directory=str(DIST_DIR / "assets")), name="assets")

    @app.get("/favicon.svg")
    async def favicon():
        return FileResponse(str(DIST_DIR / "favicon.svg"))

    @app.get("/icons.svg")
    async def icons():
        return FileResponse(str(DIST_DIR / "icons.svg"))

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        idx = DIST_DIR / "index.html"
        if idx.exists():
            from fastapi.responses import Response
            content = idx.read_bytes()
            return Response(content=content, media_type="text/html",
                            headers={"Cache-Control": "no-cache, no-store, must-revalidate",
                                     "Pragma": "no-cache", "Expires": "0"})
        return JSONResponse({"error": "Frontend not built"}, status_code=404)


def main():
    import uvicorn
    uvicorn.run("lora_api.main:app", host="0.0.0.0", port=API_PORT, reload=False)


if __name__ == "__main__":
    main()
