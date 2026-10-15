"""Thin Telegram ingress; domain work is handled by the shared services."""

import asyncio
import logging
import os
import uuid
from datetime import timedelta

from telegram import MenuButtonWebApp, Update, WebAppInfo
from telegram.ext import Application, ApplicationBuilder, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from lora_v2.config import Settings
from lora_v2.db import create_pool, migrate
from lora_v2.proactive import decide_followup, decide_proposal
from lora_v2.models import Command
from lora_v2.queries import answer_read_intent
from lora_v2.service import execute_command
from lora_v2.telegram_ingress import handle_owner_message
from lora_v2.worker import run_forever

logger = logging.getLogger(__name__)


def create_bot(settings: Settings | None = None) -> Application:
    config = settings or Settings.from_env()

    async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await handle_owner_message(update, context.application.bot_data["pool"], config)

    async def on_proposal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        if not query or not update.effective_user or update.effective_user.id != config.telegram_user_id:
            return
        parts = (query.data or "").split(":")
        if len(parts) != 4 or parts[:2] != ["v2", "p"] or parts[3] not in {"yes", "no"}:
            await query.answer("Acțiune invalidă", show_alert=True)
            return
        try:
            proposal_id = uuid.UUID(parts[2])
        except ValueError:
            await query.answer("Acțiune invalidă", show_alert=True)
            return
        result = await decide_proposal(
            context.application.bot_data["pool"], config, config.telegram_user_id,
            proposal_id, accept=parts[3] == "yes",
        )
        await query.answer()
        await query.edit_message_text(
            result.message if result else "Propunerea a fost respinsă sau nu mai este disponibilă."
        )

    async def on_followup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        if not query or not update.effective_user or update.effective_user.id != config.telegram_user_id:
            return
        parts = (query.data or "").split(":")
        if len(parts) != 4 or parts[:2] != ["v2", "f"] or parts[3] not in {"done", "tomorrow"}:
            await query.answer("Acțiune invalidă", show_alert=True)
            return
        try:
            proposal_id = uuid.UUID(parts[2])
        except ValueError:
            await query.answer("Acțiune invalidă", show_alert=True)
            return
        result = await decide_followup(
            context.application.bot_data["pool"], config, config.telegram_user_id,
            proposal_id, parts[3],
        )
        if result is None:
            await query.answer("Întrebarea nu mai este disponibilă", show_alert=True)
            return
        await query.answer(result.message, show_alert=result.status == "needs_input")
        if result.status in {"saved", "already_done"}:
            await query.edit_message_text(result.message)

    async def on_alert_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        if not query or not update.effective_user or update.effective_user.id != config.telegram_user_id:
            return
        parts = (query.data or "").split(":")
        if len(parts) != 5 or parts[:2] != ["v2", "e"] or parts[4] not in {"done", "tomorrow"}:
            await query.answer("Acțiune invalidă", show_alert=True)
            return
        try:
            entry_id, version = uuid.UUID(parts[2]), int(parts[3])
        except ValueError:
            await query.answer("Acțiune invalidă", show_alert=True)
            return
        if parts[4] == "done":
            command = Command(type="complete_entry", data={
                "entry_id": str(entry_id), "expected_version": version,
            })
        else:
            async with context.application.bot_data["pool"].acquire() as conn:
                current = await conn.fetchrow(
                    "SELECT starts_at FROM calendar_entries WHERE id=$1 AND owner_id=$2 AND version=$3",
                    entry_id, config.telegram_user_id, version,
                )
            if not current:
                await query.answer("Reminderul a fost modificat între timp", show_alert=True)
                return
            command = Command(type="reschedule_entry", data={
                "entry_id": str(entry_id),
                "starts_at": (current["starts_at"] + timedelta(days=1)).isoformat(),
                "expected_version": version,
            })
        result = await execute_command(
            context.application.bot_data["pool"], config, config.telegram_user_id,
            command, idempotency_key=f"alert:{entry_id}:v{version}:{parts[4]}",
        )
        await query.answer(result.message, show_alert=result.status == "needs_input")
        if result.status in ("saved", "already_done"):
            await query.edit_message_text(result.message)

    async def on_task_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        if not query or not update.effective_user or update.effective_user.id != config.telegram_user_id:
            return
        parts = (query.data or "").split(":")
        if len(parts) != 5 or parts[:2] != ["v2", "t"] or parts[4] != "done":
            await query.answer("Acțiune invalidă", show_alert=True)
            return
        try:
            task_id, version = uuid.UUID(parts[2]), int(parts[3])
        except ValueError:
            await query.answer("Acțiune invalidă", show_alert=True)
            return
        result = await execute_command(
            context.application.bot_data["pool"], config, config.telegram_user_id,
            Command(type="complete_task", data={"task_id": str(task_id), "expected_version": version}),
            idempotency_key=f"task_alert:{task_id}:v{version}:done",
        )
        await query.answer(result.message, show_alert=result.status == "needs_input")
        if result.status in ("saved", "already_done"):
            await query.edit_message_text(result.message)

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
    app.add_handler(CallbackQueryHandler(on_proposal, pattern=r"^v2:p:"))
    app.add_handler(CallbackQueryHandler(on_followup, pattern=r"^v2:f:"))
    app.add_handler(CallbackQueryHandler(on_alert_action, pattern=r"^v2:e:"))
    app.add_handler(CallbackQueryHandler(on_task_action, pattern=r"^v2:t:"))
    for name in ("azi", "maine", "taskuri", "cheltuieli", "facultate"):
        app.add_handler(CommandHandler(name, on_read_command))
    app.add_handler(MessageHandler((filters.TEXT | filters.PHOTO | filters.VOICE) & ~filters.COMMAND & filters.ChatType.PRIVATE, on_message))
    return app


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    create_bot().run_polling(drop_pending_updates=False)


if __name__ == "__main__":
    main()
