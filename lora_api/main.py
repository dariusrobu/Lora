import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from lora_api.config import DATABASE_URL, LORA_API_PASSWORD, JWT_SECRET, API_PORT
from lora_api.database import init_pool, close_pool, get_pool
from lora_api.auth import hash_password, verify_password, create_token, get_current_user

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("lora_api")

BASE_DIR = Path(__file__).parent.parent
DIST_DIR = BASE_DIR / "dashboard" / "dist"
SCHEMA_SQL = BASE_DIR / "db" / "schema.sql"


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is required")
    await init_pool(DATABASE_URL)
    await _ensure_schema()
    await _ensure_user_table()
    logger.info(f"API server starting on port {API_PORT}")
    yield
    await close_pool()


app = FastAPI(
    title="Lora API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
                await conn.execute(raw)
                logger.info("Executed schema.sql successfully")
            except Exception as e:
                logger.warning(f"schema.sql execution error (non-fatal): {e}")
    else:
        logger.warning(f"schema.sql not found at {SCHEMA_SQL}")

    # 2. Additional DDL (columns not in schema.sql)
    async with pool.acquire() as conn:
        for ddl in [
            "ALTER TABLE health_logs ADD COLUMN IF NOT EXISTS cigarettes INT DEFAULT 0",
            "ALTER TABLE user_profile ADD COLUMN IF NOT EXISTS llm_provider TEXT DEFAULT 'ollama'",
            "ALTER TABLE user_profile ADD COLUMN IF NOT EXISTS llm_host TEXT DEFAULT 'http://localhost:11434'",
            "ALTER TABLE user_profile ADD COLUMN IF NOT EXISTS llm_model TEXT DEFAULT 'llama3.2:3b'",
            "ALTER TABLE user_profile ADD COLUMN IF NOT EXISTS gemini_api_key TEXT",
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
                logger.warning(f"DDL skipped ({e}): {ddl}")

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


@app.get("/api/health")
async def health():
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


from lora_api.routers import tasks, projects, finance, university, shopping, health
from lora_api.routers import workout, skills, reading, nutrition, goals, mood
from lora_api.routers import memory, notes, calendar, travel, focus, weather
from lora_api.routers import insights, location, profile, homeserver, space, llm

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
