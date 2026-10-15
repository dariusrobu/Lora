"""Opt-in v2 conversation mode inside the existing Telegram polling process."""

import logging

import asyncpg
from telegram import Update
from telegram.ext import Application, ApplicationHandlerStop, ContextTypes, MessageHandler, filters

from lora_v2.config import Settings
from lora_v2.db import create_pool, migrate
from lora_v2.telegram_ingress import handle_owner_message
from lora_v2.telegram_actions import register_v2_callbacks

logger = logging.getLogger(__name__)


async def install_bridge(application: Application, settings: Settings) -> asyncpg.Pool:
    pool = await create_pool(settings)
    try:
        await migrate(pool)
    except Exception:
        await pool.close()
        raise
    mode = {"active": False}

    async def toggle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if (not update.effective_user or update.effective_user.id != settings.telegram_user_id
                or not update.message or not update.effective_chat
                or update.effective_chat.type != "private"):
            return
        mode["active"] = (update.message.text or "").split()[0].split("@")[0].lower() == "/v2on"
        logger.info("V2 Telegram conversation mode: %s", "on" if mode["active"] else "off")
        await update.message.reply_text(
            "Conversația v2 este activă. Scrie /v2off pentru a reveni la Lora veche."
            if mode["active"] else "Ai revenit la conversația Lora veche."
        )
        raise ApplicationHandlerStop

    async def bridge_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not mode["active"]:
            return
        try:
            consumed = await handle_owner_message(update, pool, settings)
        except Exception as exc:
            logger.error("V2 Telegram bridge failed: %s", type(exc).__name__)
            if update.message and update.effective_user and update.effective_user.id == settings.telegram_user_id:
                await update.message.reply_text("V2 nu a putut procesa mesajul. Încearcă din nou sau scrie /v2off.")
            raise ApplicationHandlerStop from None
        if consumed:
            raise ApplicationHandlerStop

    application.add_handler(MessageHandler(
        filters.TEXT & filters.ChatType.PRIVATE & filters.Regex(r"^/v2(?:on|off)(?:@\w+)?(?:\s|$)"),
        toggle,
    ), group=-1)
    application.add_handler(MessageHandler(
        (filters.TEXT | filters.PHOTO | filters.VOICE) & ~filters.COMMAND & filters.ChatType.PRIVATE,
        bridge_message,
    ), group=-1)
    application.bot_data["v2_pool"] = pool
    register_v2_callbacks(application, settings, group=-1, stop_after=True)
    return pool
