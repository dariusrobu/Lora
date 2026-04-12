import asyncio
import sys
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    CallbackQueryHandler,
    CommandHandler,
    filters,
)
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
from functools import partial
import os
from aiohttp import web
from core.ical import generate_user_calendar

async def handle_health_check(request):
    return web.Response(text="OK", status=200)

async def handle_calendar_request(request):
    """HTTP endpoint to serve the .ics calendar."""
    # Simple security check: token in URL
    token = request.match_info.get('token')
    # Use the first 8 characters of the Telegram Bot Token as a simple secret
    expected_token = TELEGRAM_BOT_TOKEN.split(':')[0]
    
    if token != expected_token:
        return web.Response(text="Unauthorized", status=403)

    pool = request.app['pool']
    try:
        ics_bytes = await generate_user_calendar(pool)
        return web.Response(
            body=ics_bytes,
            content_type='text/calendar',
            headers={
                'Content-Disposition': 'attachment; filename="lora_calendar.ics"'
            }
        )
    except Exception as e:
        print(f"Error serving calendar: {e}")
        return web.Response(text="Error generating calendar", status=500)

async def start_web_server(pool):
    """Starts the web server for WebCal subscription."""
    app = web.Application()
    app['pool'] = pool
    app.router.add_get('/', handle_health_check)
    app.router.add_get('/calendar/{token}', handle_calendar_request)
    
    port = int(os.environ.get("PORT", 8080))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"Web server started on port {port} (WebCal enabled)")

async def start_bot():
    print("Starting Lora initialization...", flush=True)

    # 1. Database Pool
    pool = await get_pool()
    print("Connected to database pool.")

    # 2. Ensure user_profile
    await pool.execute(
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
    print(f"User profile ensured for ID: {TELEGRAM_USER_ID}")

    # Start Web Server for WebCal
    await start_web_server(pool)

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
    application.add_handler(CommandHandler("calendar", calendar_command))
    application.add_handler(MessageHandler(filters.VOICE, voice_handler_with_pool))
    application.add_handler(MessageHandler(filters.ALL, msg_handler_with_pool))
    application.add_handler(CallbackQueryHandler(cb_handler_with_pool))

    print("Lora is ready. Starting polling... 🤖")

    # Manual async startup to avoid event loop conflicts
    await application.initialize()
    await application.start()
    
    # Wait a bit to allow previous instance to disconnect (important for Render zero-downtime)
    print("⏳ Aștept 10 secunde pentru a asigura deconectarea instanțelor vechi...", flush=True)
    await asyncio.sleep(10)
    
    await application.updater.start_polling(
        drop_pending_updates=True,
        allowed_updates=["message", "callback_query"],
    )

    # Keep the bot running until interrupted
    try:
        print("Loop principal activ. Lora ascultă... 🚀", flush=True)
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, asyncio.CancelledError):
        print("Stopping...")
    finally:
        await application.updater.stop()
        await application.stop()
        await application.shutdown()
        await close_pool()
        print("Database pool closed. Shutdown complete.")


if __name__ == "__main__":
    import sys

    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)

    asyncio.run(start_bot())
