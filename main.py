import asyncio
import sys
import os
from pathlib import Path
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
)
from modules.skills import skills_command
from functools import partial

PID_FILE = Path(__file__).parent / "lora.pid"


def acquire_pid_lock():
    """Prevents running multiple instances of the bot simultaneously."""
    if PID_FILE.exists():
        old_pid = PID_FILE.read_text().strip()
        try:
            os.kill(int(old_pid), 0)
            print(
                f"ERROR: Bot already running with PID {old_pid}. Exiting.", flush=True
            )
            sys.exit(1)
        except (ProcessLookupError, ValueError):
            print(f"Stale PID file found (PID {old_pid}). Removing.", flush=True)
    PID_FILE.write_text(str(os.getpid()))
    print(f"PID lock acquired: {os.getpid()}", flush=True)


def release_pid_lock():
    """Cleans up the PID file on shutdown."""
    if PID_FILE.exists():
        PID_FILE.unlink()


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
    application.add_handler(MessageHandler(filters.VOICE, voice_handler_with_pool))
    application.add_handler(MessageHandler(filters.ALL, msg_handler_with_pool))
    application.add_handler(CallbackQueryHandler(cb_handler_with_pool))

    print("Lora is ready. Starting polling... 🤖")

    async with application:
        await application.initialize()
        await application.start()
        await application.updater.start_polling(
            drop_pending_updates=True, allowed_updates=["message", "callback_query"]
        )

        # Keep the bot running
        print("Polling active.")
        try:
            # Simple wait loop to keep the async function alive while polling
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

    acquire_pid_lock()

    try:
        asyncio.run(start_bot())
    except KeyboardInterrupt:
        pass
    finally:
        release_pid_lock()
