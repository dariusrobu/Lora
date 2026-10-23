"""Shared v2 Telegram callback actions for standalone and legacy polling."""

import os
import uuid
from datetime import timedelta

from telegram import Update
from telegram.ext import Application, ApplicationHandlerStop, CallbackQueryHandler, ContextTypes

from lora_v2.config import Settings
from lora_v2.models import Command
from lora_v2.proactive import decide_followup, decide_proposal
from lora_v2.queries import answer_read_intent
from lora_v2.service import execute_command
from lora_v2.telegram_navigation import READ_INTENTS, navigation_keyboard


def register_v2_callbacks(
    app: Application, config: Settings, group: int = 0, stop_after: bool = False,
) -> None:
    async def on_navigation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        if not query or not update.effective_user or update.effective_user.id != config.telegram_user_id:
            return
        intent = (query.data or "").removeprefix("v2:n:")
        if intent not in READ_INTENTS:
            await query.answer("Acțiune invalidă", show_alert=True)
            return
        await query.answer()
        answer = await answer_read_intent(
            context.application.bot_data["v2_pool"], config, config.telegram_user_id, intent,
        )
        if len(answer) > 3900:
            answer = answer[:3850].rsplit("\n", 1)[0] + "\n… Restul este în Mini App."
        await query.edit_message_text(
            answer, reply_markup=navigation_keyboard(intent, os.getenv("LORA_V2_MINI_APP_URL", "")),
        )

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
            context.application.bot_data["v2_pool"], config, config.telegram_user_id,
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
            context.application.bot_data["v2_pool"], config, config.telegram_user_id,
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
            async with context.application.bot_data["v2_pool"].acquire() as conn:
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
            context.application.bot_data["v2_pool"], config, config.telegram_user_id,
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
            context.application.bot_data["v2_pool"], config, config.telegram_user_id,
            Command(type="complete_task", data={"task_id": str(task_id), "expected_version": version}),
            idempotency_key=f"task_alert:{task_id}:v{version}:done",
        )
        await query.answer(result.message, show_alert=result.status == "needs_input")
        if result.status in ("saved", "already_done"):
            await query.edit_message_text(result.message)

    def wrap(callback):
        async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
            await callback(update, context)
            if stop_after and update.effective_user and update.effective_user.id == config.telegram_user_id:
                raise ApplicationHandlerStop
        return wrapped

    app.add_handler(CallbackQueryHandler(wrap(on_proposal), pattern=r"^v2:p:"), group=group)
    app.add_handler(CallbackQueryHandler(wrap(on_followup), pattern=r"^v2:f:"), group=group)
    app.add_handler(CallbackQueryHandler(wrap(on_alert_action), pattern=r"^v2:e:"), group=group)
    app.add_handler(CallbackQueryHandler(wrap(on_task_action), pattern=r"^v2:t:"), group=group)
    app.add_handler(CallbackQueryHandler(wrap(on_navigation), pattern=r"^v2:n:"), group=group)
