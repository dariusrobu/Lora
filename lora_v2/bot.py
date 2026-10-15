"""Thin Telegram ingress; domain work is handled by the shared services."""

import asyncio
import logging
import os

from telegram import MenuButtonWebApp, Update, WebAppInfo
from telegram.ext import Application, ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

from lora_v2.config import Settings
from lora_v2.db import create_pool, migrate
from lora_v2.queries import answer_read_intent
from lora_v2.telegram_ingress import handle_owner_message
from lora_v2.telegram_actions import register_v2_callbacks
from lora_v2.worker import run_forever

logger = logging.getLogger(__name__)


def create_bot(settings: Settings | None = None) -> Application:
    config = settings or Settings.from_env()

    async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await handle_owner_message(update, context.application.bot_data["pool"], config)

    async def on_read_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message or not update.effective_user or update.effective_user.id != config.telegram_user_id:
            return
        command = (update.message.text or "").split()[0].split("@")[0].lower()
        intent = {
            "/azi": "today", "/maine": "tomorrow", "/taskuri": "tasks",
            "/cheltuieli": "expenses", "/facultate": "university",
        }.get(command)
        if intent:
            await update.message.reply_text(await answer_read_intent(
                context.application.bot_data["pool"], config, config.telegram_user_id, intent,
            ))

    async def post_init(application: Application) -> None:
        pool = await create_pool(config)
        await migrate(pool)
        application.bot_data["pool"] = pool
        application.bot_data["v2_pool"] = pool
        application.bot_data["worker"] = asyncio.create_task(run_forever(pool, application.bot, config))
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

    app = ApplicationBuilder().token(config.telegram_bot_token).post_init(post_init).post_shutdown(post_shutdown).build()
    register_v2_callbacks(app, config)
    for name in ("azi", "maine", "taskuri", "cheltuieli", "facultate"):
        app.add_handler(CommandHandler(name, on_read_command))
    app.add_handler(MessageHandler((filters.TEXT | filters.PHOTO | filters.VOICE) & ~filters.COMMAND & filters.ChatType.PRIVATE, on_message))
    return app


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    create_bot().run_polling(drop_pending_updates=False)


if __name__ == "__main__":
    main()
