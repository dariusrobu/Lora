"""Thin Telegram ingress; domain work is handled by the shared services."""

import asyncio
import logging
import os

from telegram import BotCommand, MenuButtonWebApp, Update, WebAppInfo
from telegram.ext import Application, ApplicationBuilder, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from lora_v2.config import Settings
from lora_v2.db import create_pool, migrate
from lora_v2.queries import answer_read_intent
from lora_v2.telegram_ingress import handle_owner_message
from lora_v2.telegram_actions import register_v2_callbacks
from lora_v2.telegram_navigation import COMMAND_INTENTS, MENU_COMMANDS
from lora_v2.worker import run_forever
from lora_v2.notifications import queue_reply
from lora_v2.telegram_read_format import format_read_summary

logger = logging.getLogger(__name__)


def create_bot(settings: Settings | None = None) -> Application:
    config = settings or Settings.from_env()

    async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await handle_owner_message(update, context.application.bot_data["pool"], config)

    async def on_read_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message or not update.effective_user or update.effective_user.id != config.telegram_user_id:
            return
        command = (update.message.text or "").split()[0].split("@")[0].lower()
        intent = COMMAND_INTENTS.get(command.removeprefix("/"))
        if intent:
            pool = context.application.bot_data["pool"]
            plain = await answer_read_intent(pool, config, config.telegram_user_id, intent)
            await queue_reply(pool, config.telegram_user_id, str(update.update_id),
                              format_read_summary(intent, plain), navigation=intent,
                              mini_app_url=os.getenv("LORA_V2_MINI_APP_URL", ""), parse_mode="HTML")

    async def post_init(application: Application) -> None:
        pool = await create_pool(config)
        await migrate(pool)
        application.bot_data["pool"] = pool
        application.bot_data["v2_pool"] = pool
        if os.getenv("LORA_V2_BOT_WORKER_ENABLED", "true").lower() == "true":
            application.bot_data["worker"] = asyncio.create_task(run_forever(pool, application.bot, config))
        await application.bot.set_my_commands([
            BotCommand(command, description) for command, description in MENU_COMMANDS
        ])
        mini_app_url = os.getenv("LORA_V2_MINI_APP_URL", "")
        if mini_app_url:
            await application.bot.set_chat_menu_button(
                chat_id=config.telegram_user_id,
                menu_button=MenuButtonWebApp(text="Lora", web_app=WebAppInfo(url=mini_app_url)),
            )

    async def post_shutdown(application: Application) -> None:
        task = application.bot_data.get("worker")
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        pool = application.bot_data.get("pool")
        if pool:
            await pool.close()

    async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if update.message and update.effective_user and update.effective_user.id == config.telegram_user_id:
            await queue_reply(context.application.bot_data["pool"], config.telegram_user_id, str(update.update_id),
                "Lora v2 este activă. Scrie natural ce vrei să notez sau trimite o fotografie ori un mesaj vocal. "
                "Calendarul și datele sunt în butonul Lora.\n"
                "Comenzi: /azi, /calendar, /taskuri, /remindere, /facultate, "
                "/noutati, /bani, /antrenament. /maine, /sold și /cheltuieli rămân disponibile."
            )

    async def old_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if update.callback_query and update.effective_user and update.effective_user.id == config.telegram_user_id:
            await update.callback_query.answer("Acest buton aparține versiunii vechi. Deschide Lora din meniu.", show_alert=True)

    async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        logger.error("Telegram update failed: %s", type(context.error).__name__)
        if isinstance(update, Update) and update.effective_user and update.effective_user.id == config.telegram_user_id:
            await queue_reply(context.application.bot_data["pool"], config.telegram_user_id,
                              'error:' + str(update.update_id), "Nu am putut procesa cererea. Te rog să reîncerci.")

    app = ApplicationBuilder().token(config.telegram_bot_token).post_init(post_init).post_shutdown(post_shutdown).build()
    app.add_error_handler(on_error)
    register_v2_callbacks(app, config)
    app.add_handler(CallbackQueryHandler(old_button))
    for name in COMMAND_INTENTS:
        app.add_handler(CommandHandler(name, on_read_command))
    app.add_handler(MessageHandler(filters.COMMAND & filters.ChatType.PRIVATE, help_command))
    app.add_handler(MessageHandler((filters.TEXT | filters.PHOTO | filters.VOICE) & ~filters.COMMAND & filters.ChatType.PRIVATE, on_message))
    return app


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    create_bot().run_polling(drop_pending_updates=False)


if __name__ == "__main__":
    main()
