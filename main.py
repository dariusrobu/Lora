import asyncio

# Deployment trigger: 2026-05-10 12:53
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
    profile_handler,
    location_handler,
    focus_command,
    stopfocus_command,
    timeblock_command,
    uni_command,
    workout_command,
    goals_command,
    health_command,
    finance_command,
    tasks_command,
    debug_app_command,
    projects_command,
    reading_command,
    memory_command,
    set_home_command,
    save_location_command,
    list_locations_command,
    location_status_command,
)
from modules.skills import skills_command
from api.routes import setup_api_routes
from core.stats import get_uptime, LAST_MESSAGE_AT

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


async def health_check(request):
    """Simple health check endpoint for Render keep-alive."""
    return web.Response(text="OK", status=200)


async def handle_health_check(request):
    """Detailed health check endpoint."""
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
        "last_message_at": LAST_MESSAGE_AT.isoformat() if LAST_MESSAGE_AT else None,
    }
    return web.json_response(status_data)


@web.middleware
async def cors_middleware(request, handler):
    """Enables CORS for all API requests."""
    # Handle preflight (OPTIONS) requests
    if request.method == "OPTIONS":
        response = web.Response(status=204)
    else:
        response = await handler(request)

    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = (
        "GET, POST, PATCH, DELETE, OPTIONS"
    )
    response.headers["Access-Control-Allow-Headers"] = (
        "Content-Type, Authorization, Lora-Api-Secret, X-Lora-Secret"
    )
    response.headers["Access-Control-Allow-Credentials"] = "true"
    return response


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


async def cmd_hub(update, context):
    """Send a direct link to the Lora Hub."""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

    dashboard_url = os.getenv("DASHBOARD_URL")
    if not dashboard_url:
        await update.message.reply_text("❌ DASHBOARD_URL nu este setată în Render.")
        return

    keyboard = [
        [
            InlineKeyboardButton(
                "📊 Deschide Lora Hub", web_app=WebAppInfo(url=dashboard_url)
            )
        ]
    ]
    await update.message.reply_text(
        "Apasă butonul de mai jos pentru a accesa dashboard-ul tău executiv:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def start_bot():
    print("Starting Lora initialization (HYBRID MODE)...", flush=True)

    # 1. Database Pool
    pool = await get_pool()
    print("Connected to database pool.")

    # 2. Schema Integrity & Migrations
    async with pool.acquire() as conn:
        # Geofencing & Location Columns
        await conn.execute("""
            ALTER TABLE user_profile ADD COLUMN IF NOT EXISTS home_latitude NUMERIC;
            ALTER TABLE user_profile ADD COLUMN IF NOT EXISTS home_longitude NUMERIC;
            ALTER TABLE user_profile ADD COLUMN IF NOT EXISTS is_at_home BOOLEAN DEFAULT TRUE;
            ALTER TABLE user_profile ADD COLUMN IF NOT EXISTS latitude NUMERIC;
            ALTER TABLE user_profile ADD COLUMN IF NOT EXISTS longitude NUMERIC;
            ALTER TABLE user_profile ADD COLUMN IF NOT EXISTS city_name TEXT;
            ALTER TABLE user_profile ADD COLUMN IF NOT EXISTS current_location_name TEXT;
            ALTER TABLE health_logs ADD COLUMN IF NOT EXISTS cigarettes INT DEFAULT 0;
        """)

        # Saved Locations Table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS saved_locations (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                name TEXT NOT NULL,
                latitude NUMERIC NOT NULL,
                longitude NUMERIC NOT NULL,
                radius_meters INT DEFAULT 200,
                created_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(user_id, name)
            );
            CREATE INDEX IF NOT EXISTS idx_saved_locations_user ON saved_locations(user_id);
        """)

        # Travel Items Table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS travel_items (
                id SERIAL PRIMARY KEY,
                item TEXT NOT NULL,
                list_name TEXT NOT NULL DEFAULT 'General',
                category TEXT,
                is_packed BOOLEAN DEFAULT FALSE,
                trip_type TEXT DEFAULT 'both',
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_travel_items_list ON travel_items(list_name);
            ALTER TABLE travel_items ADD COLUMN IF NOT EXISTS category TEXT;
            ALTER TABLE travel_items ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW();
        """)

        # User Profile Init (Safe now that columns exist)
        await conn.execute(
            """
            INSERT INTO user_profile (telegram_id, timezone, morning_time, eod_time, is_at_home)
            VALUES ($1, $2, $3, $4, TRUE)
            ON CONFLICT (telegram_id) DO NOTHING
            """,
            TELEGRAM_USER_ID,
            TIMEZONE,
            MORNING_BRIEFING_TIME,
            EOD_REFLECTION_TIME,
        )

        # Semester Config Init
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
        print(
            f"⚠️ Warning: Some modules failed health check: {', '.join(bad_modules)}",
            flush=True,
        )
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
    location_handler_with_pool = partial(location_handler, pool=pool)

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
    application.add_handler(CommandHandler("hub", cmd_hub))
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
    application.add_handler(
        CommandHandler("sethome", partial(set_home_command, pool=pool))
    )
    application.add_handler(
        CommandHandler("save", partial(save_location_command, pool=pool))
    )
    application.add_handler(
        CommandHandler("locations", partial(list_locations_command, pool=pool))
    )
    application.add_handler(
        CommandHandler("location", partial(location_status_command, pool=pool))
    )
    application.add_handler(
        CommandHandler(
            "briefing", partial(message_handler, pool=pool, text="/briefing")
        )
    )
    application.add_handler(CommandHandler("debug_app", debug_app_command))
    application.add_handler(CommandHandler("projects", projects_command))

    # 6. Startup 'Catch-up' for Morning Briefing
    async def startup_check():
        await asyncio.sleep(10)  # Wait for bot to stabilize
        from scheduler.jobs import check_wake_time_and_schedule

        await check_wake_time_and_schedule(application, pool)
        print("🚀 Startup briefing catch-up check completed.")

    asyncio.create_task(startup_check())
    application.add_handler(CommandHandler("reading", reading_command))
    application.add_handler(
        CommandHandler("eod", partial(message_handler, pool=pool, text="/eod"))
    )
    application.add_handler(
        CommandHandler(
            "lastweek", partial(message_handler, pool=pool, text="/lastweek")
        )
    )
    application.add_handler(MessageHandler(filters.VOICE, voice_handler_with_pool))
    application.add_handler(MessageHandler(filters.PHOTO, photo_handler_with_pool))
    # Support both normal Share Location and Live Location updates (edited messages)
    application.add_handler(
        MessageHandler(filters.LOCATION, location_handler_with_pool)
    )
    application.add_handler(
        MessageHandler(
            filters.UpdateType.EDITED_MESSAGE & filters.LOCATION,
            location_handler_with_pool,
        )
    )
    application.add_handler(MessageHandler(filters.ALL, msg_handler_with_pool))
    application.add_handler(CallbackQueryHandler(cb_handler_with_pool))

    @web.middleware
    async def cors_middleware(request, handler):
        if request.method == "OPTIONS":
            response = web.Response(status=204)
        else:
            response = await handler(request)

        origin = request.headers.get("Origin", "*")
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Methods"] = (
            "GET, POST, PATCH, PUT, DELETE, OPTIONS"
        )
        response.headers["Access-Control-Allow-Headers"] = (
            "Content-Type, Authorization, X-Internal-Secret, Bypass-Tunnel-Reminder, Lora-Api-Secret"
        )
        response.headers["Access-Control-Allow-Credentials"] = "true"
        return response

    # API Routes
    routes = web.RouteTableDef()

    @web.middleware
    async def log_middleware(request, handler):
        response = await handler(request)
        print(f"🌐 {request.method} {request.path} -> {response.status}", flush=True)
        return response

    # 6. Web Server for Health Check & Dashboard (runs in background)
    dist_path = os.path.join(os.path.dirname(__file__), "dashboard", "dist")

    async def handle_debug(request):
        """Debug endpoint for dashboard connectivity."""
        dist_exists = os.path.exists(dist_path)
        return web.json_response(
            {
                "status": "online",
                "cors": "enabled",
                "api_secret_set": bool(os.getenv("LORA_API_SECRET")),
                "dashboard_dist": dist_exists,
                "files": os.listdir(dist_path) if dist_exists else [],
            }
        )

    async def serve_dashboard_index(request):
        index_file = os.path.join(dist_path, "index.html")
        print(f"📄 Request for dashboard. Looking for: {index_file}", flush=True)
        if os.path.exists(index_file):
            return web.FileResponse(index_file)

        # Diagnostic help
        error_msg = f"Dashboard build not found at {dist_path}. "
        if not os.path.exists(dist_path):
            error_msg += "Folder does not exist."
        else:
            error_msg += (
                f"Folder exists but index.html missing. Files: {os.listdir(dist_path)}"
            )

        return web.Response(text=error_msg, status=404)

    app = web.Application(middlewares=[cors_middleware, log_middleware])
    app["pool"] = pool
    app.router.add_get("/health", health_check)
    app.router.add_get("/api/health", handle_health_check)
    app.router.add_get("/api/debug", handle_debug)
    setup_api_routes(app)

    async def serve_welcome(request):
        return web.Response(
            text="🚀 Lora Bot is ONLINE\n\nDiagnostic links:\n- /api/health\n- /api/debug\n- /api/projects\n\nDashboard is served from /",
            content_type="text/plain",
        )

    if os.path.exists(dist_path):
        app.router.add_get("/", serve_dashboard_index)
        app.router.add_static(
            "/assets", os.path.join(dist_path, "assets"), name="dashboard_assets"
        )
        for f in ["favicon.ico", "favicon.svg", "manifest.json"]:
            if os.path.exists(os.path.join(dist_path, f)):
                app.router.add_get(
                    f"/{f}", lambda r, f=f: web.FileResponse(os.path.join(dist_path, f))
                )
    else:
        # Fallback if dashboard files are not in this service
        app.router.add_get("/", serve_welcome)

    port = int(os.environ.get("PORT", 8083))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"Web server active on port {port}", flush=True)

    # 7. Start Telegram Bot
    # Remove any existing webhook and ensure clean state
    try:
        await application.bot.delete_webhook(drop_pending_updates=True)
        print("Webhook deleted (dropped updates).", flush=True)
    except Exception as e:
        print(f"Warning: webhook delete failed: {e}", flush=True)

    await application.initialize()

    # Set the Main Menu Button to open the Dashboard (served by Bot)
    bot_domain = os.getenv("WEB_DOMAIN", "lora-bot-tgbi.onrender.com")
    dashboard_url = f"https://{bot_domain}/"

    try:
        from telegram import MenuButtonWebApp, WebAppInfo

        await application.bot.set_chat_menu_button(
            chat_id=TELEGRAM_USER_ID,
            menu_button=MenuButtonWebApp(
                text="Lora Hub", web_app=WebAppInfo(url=dashboard_url)
            ),
        )
        print(f"✅ Main Menu Button set to: {dashboard_url}", flush=True)
    except Exception as e:
        print(f"Error setting menu button: {e}", flush=True)

    await application.start()

    # Increased delay for Render to clear old instances
    print("⏳ Waiting 15s for old instances to clear (Anti-Conflict)...", flush=True)
    await asyncio.sleep(15)

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

    # Prevent multiple bot instances from running
    check_pid_lock()

    asyncio.run(start_bot())
