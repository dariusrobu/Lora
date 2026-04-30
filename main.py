import asyncio
import sys
import logging
import os
from datetime import date
from functools import partial
from aiohttp import web
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    CallbackQueryHandler,
    CommandHandler,
    filters,
)

# 1. Internal Modules
from core.config import (
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_USER_ID,
    TIMEZONE,
    MORNING_BRIEFING_TIME,
    EOD_REFLECTION_TIME,
    CALENDAR_SECRET,
)
from db.connection import get_pool, close_pool
from bot.handler import (
    message_handler,
    callback_handler,
    voice_handler,
    photo_handler,
    profile_handler,
    focus_command,
    stopfocus_command,
    timeblock_command,
    uni_command,
    workout_command,
    goals_command,
    health_command,
    finance_command,
    tasks_command,
    projects_command,
    reading_command,
    calendar_command,
    memory_command,
)
from modules.skills import skills_command
from core.ical import generate_user_calendar
from api.routes import setup_api_routes
from core.stats import get_uptime, LAST_MESSAGE_AT
from core.gemini import _api_available

# 2. Setup Logging — rotating file (2 MB × 3) + stdout stream
from logging.handlers import RotatingFileHandler

_log_formatter = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
_file_handler = RotatingFileHandler(
    "bot.log", maxBytes=2 * 1024 * 1024, backupCount=3, encoding="utf-8"
)
_file_handler.setFormatter(_log_formatter)
_stream_handler = logging.StreamHandler(sys.stdout)
_stream_handler.setFormatter(_log_formatter)

logging.basicConfig(
    level=logging.INFO,
    handlers=[_stream_handler, _file_handler],
)
logger = logging.getLogger(__name__)


async def handle_health_check(request):
    """
    Detailed health check endpoint.
    Returns JSON with DB status, Gemini status, and uptime.
    """
    pool = request.app.get("pool")
    db_status = "error"
    if pool:
        try:
            async with pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
                db_status = "connected"
        except Exception as e:
            print(f"Health check DB error: {e}")
            db_status = "error"

    from core.gemini import _api_available as gemini_available
    
    status_data = {
        "status": "ok",
        "db": db_status,
        "gemini": "available" if gemini_available else "unavailable",
        "uptime_seconds": get_uptime(),
        "last_message_at": LAST_MESSAGE_AT.isoformat() if LAST_MESSAGE_AT else None
    }
    
    return web.json_response(status_data)


async def handle_calendar_request(request):
    """HTTP endpoint to serve the .ics calendar."""
    # Secure token comparison — never derived from the public bot ID
    token = request.match_info.get("token")
    if not token or token != CALENDAR_SECRET:
        return web.Response(text="Unauthorized", status=403)

    pool = request.app["pool"]
    try:
        ics_bytes = await generate_user_calendar(pool)
        return web.Response(
            body=ics_bytes,
            content_type="text/calendar",
            headers={"Content-Disposition": 'attachment; filename="lora_calendar.ics"'},
        )
    except Exception as e:
        import traceback

        traceback.print_exc()
        print(f"Error serving calendar: {e}")
        return web.Response(text=f"Error generating calendar: {e}", status=500)


PID_FILE = "lora.pid"


def check_pid_lock():
    """Prevents multiple bot instances from running simultaneously."""
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE) as f:
                content = f.read().strip()
                if not content:
                    existing_pid = -1
                else:
                    existing_pid = int(content)
            
            if existing_pid == os.getpid():
                return
            
            try:
                # Signal 0 checks if the process is alive without killing it
                os.kill(existing_pid, 0)
                # Process is alive — another instance is running, abort
                print(
                    f"FATAL: Another Lora instance is already running (PID {existing_pid}). Exiting."
                )
                sys.exit(1)
            except ProcessLookupError:
                pass
        except (ValueError, Exception):
            pass

    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))



# 10. Start the bot


async def start_bot():
    print("Starting Lora initialization (HYBRID MODE)...", flush=True)

    # 1. Database Pool
    pool = await get_pool()
    print("Connected to database pool.")

    # 2. Ensure user_profile and semester_config
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO user_profile (telegram_id, timezone, morning_time, eod_time)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (telegram_id) DO NOTHING
            """,
            TELEGRAM_USER_ID,
            TIMEZONE,
            MORNING_BRIEFING_TIME,
            EOD_REFLECTION_TIME,
        )

        # Ensure semester_config exists
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS semester_config (
                id SERIAL PRIMARY KEY,
                semester_start DATE NOT NULL,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)

        # Ensure calendar_sync exists
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS calendar_sync (
                id              SERIAL PRIMARY KEY,
                lora_type       TEXT NOT NULL,
                lora_id         INTEGER,
                ical_uid        TEXT UNIQUE,
                summary         TEXT,
                synced_at       TIMESTAMP DEFAULT NOW(),
                last_modified   TIMESTAMP DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_calendar_sync_uid ON calendar_sync(ical_uid);
            CREATE INDEX IF NOT EXISTS idx_calendar_sync_lora ON calendar_sync(lora_type, lora_id);
        """)

        exists = await conn.fetchval("SELECT EXISTS (SELECT 1 FROM semester_config)")
        if not exists:
            from core.config import SEMESTER_START_DATE
            from datetime import datetime

            try:
                start_date = datetime.strptime(SEMESTER_START_DATE, "%Y-%m-%d").date()
            except ValueError:
                start_date = date(2026, 2, 23)

            await conn.execute(
                "INSERT INTO semester_config (semester_start) VALUES ($1)",
                start_date,
            )

    # 3. Module Health Check
    from core.router import check_module_health
    health_status = await check_module_health()
    bad_modules = [m for m, s in health_status.items() if s != "ok"]
    if bad_modules:
        print(f"⚠️ Warning: Some modules failed health check: {', '.join(bad_modules)}", flush=True)
    else:
        print("✅ All core modules ready.", flush=True)

    # 4. Build the Application
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    application.bot_data["pool"] = pool

    # 4. Initialize Scheduler
    from scheduler.jobs import setup_scheduler

    setup_scheduler(application, pool)

    # 5. Register handlers
    msg_handler_with_pool = partial(message_handler, pool=pool)
    cb_handler_with_pool = partial(callback_handler, pool=pool)
    voice_handler_with_pool = partial(voice_handler, pool=pool)
    photo_handler_with_pool = partial(photo_handler, pool=pool)

    application.add_handler(CommandHandler("calendar", calendar_command))
    application.add_handler(
        CommandHandler("profile", partial(profile_handler, pool=pool))
    )
    application.add_handler(
        CommandHandler(
            "test_calendar", partial(message_handler, pool=pool, text="/test_calendar")
        )
    )
    application.add_handler(
        CommandHandler(
            "sync_calendar", partial(message_handler, pool=pool, text="/sync_calendar")
        )
    )
    application.add_handler(CommandHandler("focus", focus_command))
    application.add_handler(CommandHandler("stopfocus", stopfocus_command))
    application.add_handler(CommandHandler("timeblock", timeblock_command))
    application.add_handler(CommandHandler("uni", uni_command))
    application.add_handler(CommandHandler("workout", workout_command))
    application.add_handler(CommandHandler("goals", goals_command))
    application.add_handler(CommandHandler("skills", skills_command))
    application.add_handler(CommandHandler("health", health_command))
    application.add_handler(CommandHandler("finance", finance_command))
    application.add_handler(CommandHandler("memory", memory_command))
    application.add_handler(CommandHandler("tasks", tasks_command))
    application.add_handler(CommandHandler("projects", projects_command))
    application.add_handler(CommandHandler("reading", reading_command))
    application.add_handler(
        CommandHandler(
            "eod", partial(message_handler, pool=pool, text="/eod")
        )
    )
    application.add_handler(
        CommandHandler(
            "lastweek", partial(message_handler, pool=pool, text="/lastweek")
        )
    )
    application.add_handler(MessageHandler(filters.VOICE, voice_handler_with_pool))
    application.add_handler(MessageHandler(filters.PHOTO, photo_handler_with_pool))
    application.add_handler(MessageHandler(filters.ALL, msg_handler_with_pool))
    application.add_handler(CallbackQueryHandler(cb_handler_with_pool))

    # 6. Web Server for Health Check & Calendar (runs in background)
    app = web.Application()
    app["pool"] = pool
    app.router.add_get("/", handle_health_check)
    app.router.add_get("/calendar/{token}", handle_calendar_request)
    setup_api_routes(app)

    port = int(os.environ.get("PORT", 8082))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"Web server active on port {port} (Health check detail enabled)", flush=True)

    # 7. Start Telegram Bot (Polling mode)
    # Remove any existing webhook and ensure clean state
    try:
        await application.bot.delete_webhook(drop_pending_updates=False)
        print("Webhook deleted.", flush=True)
    except Exception as e:
        print(f"Warning: webhook delete failed: {e}", flush=True)

    await application.initialize()
    await application.start()

    # Small delay to avoid conflict with old instances
    print("⏳ Waiting 10s for old instances to clear...", flush=True)
    await asyncio.sleep(10)

    await application.updater.start_polling(drop_pending_updates=False)
    print("Lora is LIVE via Polling 🚀", flush=True)

    try:
        # Keep running
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, asyncio.CancelledError):
        print("Stopping...")
    finally:
        await application.updater.stop()
        await application.stop()
        await application.shutdown()
        await runner.cleanup()
        await close_pool()
        if os.path.exists(PID_FILE):
            os.remove(PID_FILE)
            print("PID lock removed.", flush=True)


if __name__ == "__main__":
    import sys

    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)

    # Prevent multiple bot instances from running
    # check_pid_lock()

    asyncio.run(start_bot())
