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
)
from db.connection import get_pool, close_pool
from bot.handler import (
    message_handler,
    callback_handler,
    voice_handler,
    photo_handler,
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
)
from modules.skills import skills_command
from core.ical import generate_user_calendar
from api.routes import setup_api_routes

# 2. Setup Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


async def handle_health_check(request):
    return web.Response(text="OK", status=200)


async def handle_calendar_request(request):
    """HTTP endpoint to serve the .ics calendar."""
    print(
        f"DEBUG: Received calendar request for token: {request.match_info.get('token')}"
    )
    # Simple security check: token in URL
    token = request.match_info.get("token")
    # Use the first 8 characters of the Telegram Bot Token as a simple secret
    expected_token = TELEGRAM_BOT_TOKEN.split(":")[0]

    if token != expected_token:
        print(f"DEBUG: Unauthorized request. Expected {expected_token}, got {token}")
        return web.Response(text="Unauthorized", status=403)

    pool = request.app["pool"]
    try:
        ics_bytes = await generate_user_calendar(pool)
        print(f"DEBUG: Successfully generated calendar ({len(ics_bytes)} bytes)")
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
    """Prevents multiple bot instances from running."""
    # First, remove any stale PID file from previous crash/restart
    if os.path.exists(PID_FILE):
        os.remove(PID_FILE)
        print("Removed stale PID file.")

    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))


# Prevent multiple bot instances from running
check_pid_lock()


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
        exists = await conn.fetchval("SELECT EXISTS (SELECT 1 FROM semester_config)")
        if not exists:
            await conn.execute(
                "INSERT INTO semester_config (semester_start) VALUES ($1)",
                date(2026, 2, 23),
            )

    # 3. Build the Application
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
    application.add_handler(CommandHandler("test_calendar", partial(message_handler, pool=pool, text="/test_calendar")))
    application.add_handler(CommandHandler("sync_calendar", partial(message_handler, pool=pool, text="/sync_calendar")))
    application.add_handler(CommandHandler("focus", focus_command))
    application.add_handler(CommandHandler("stopfocus", stopfocus_command))
    application.add_handler(CommandHandler("timeblock", timeblock_command))
    application.add_handler(CommandHandler("uni", uni_command))
    application.add_handler(CommandHandler("workout", workout_command))
    application.add_handler(CommandHandler("goals", goals_command))
    application.add_handler(CommandHandler("skills", skills_command))
    application.add_handler(CommandHandler("health", health_command))
    application.add_handler(CommandHandler("finance", finance_command))
    application.add_handler(CommandHandler("tasks", tasks_command))
    application.add_handler(CommandHandler("projects", projects_command))
    application.add_handler(CommandHandler("reading", reading_command))
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

    port = int(os.environ.get("PORT", 8080))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"Web server active on port {port} (Health check OK)", flush=True)

    # 7. Start Telegram Bot (Polling mode)
    # Remove any existing webhook and ensure clean state
    try:
        await application.bot.delete_webhook(drop_pending_updates=True)
        print("Webhook deleted.", flush=True)
    except Exception as e:
        print(f"Warning: webhook delete failed: {e}", flush=True)

    await application.initialize()
    await application.start()

    # Small delay to avoid conflict with old instances
    print("⏳ Waiting 10s for old instances to clear...", flush=True)
    await asyncio.sleep(10)

    await application.updater.start_polling(drop_pending_updates=True)
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

    asyncio.run(start_bot())
