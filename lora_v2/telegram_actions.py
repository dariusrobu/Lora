"""Shared v2 Telegram callback actions for standalone and legacy polling."""

import os
import uuid
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from telegram import Update
from telegram.ext import Application, ApplicationHandlerStop, CallbackQueryHandler, ContextTypes

from lora_v2.config import Settings
from lora_v2.models import Command
from lora_v2.proactive import decide_followup, decide_proposal
from lora_v2.queries import answer_read_intent
from lora_v2.telegram_read_format import format_read_summary
from lora_v2.service import execute_command
from lora_v2.telegram_navigation import READ_INTENTS, navigation_keyboard
from lora_v2.telegram_quick_actions import (
    action_menu, add_prompt, category_menu, change_expense_category,
    item_detail, record_class_attendance,
)


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
        plain = await answer_read_intent(
            context.application.bot_data["v2_pool"], config, config.telegram_user_id, intent,
        )
        answer = format_read_summary(intent, plain)
        await query.edit_message_text(
            answer, reply_markup=navigation_keyboard(intent, os.getenv("LORA_V2_MINI_APP_URL", "")),
            parse_mode="HTML",
        )

    async def on_action_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        if not query or not update.effective_user or update.effective_user.id != config.telegram_user_id:
            return
        parts = (query.data or "").split(":")
        if len(parts) not in {3, 4} or parts[:2] != ["v2", "a"] or parts[2] not in READ_INTENTS:
            await query.answer("Acțiune invalidă", show_alert=True)
            return
        try:
            page = int(parts[3]) if len(parts) == 4 else 0
        except ValueError:
            await query.answer("Acțiune invalidă", show_alert=True)
            return
        if page < 0 or page > 20 or (parts[2] in {"today", "tomorrow"} and page != 0):
            await query.answer("Acțiune invalidă", show_alert=True)
            return
        text, keyboard = await action_menu(
            context.application.bot_data["v2_pool"], config, config.telegram_user_id, parts[2], page,
        )
        await query.answer()
        await query.edit_message_text(text, reply_markup=keyboard)

    async def on_item(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        if not query or not update.effective_user or update.effective_user.id != config.telegram_user_id:
            return
        parts = (query.data or "").split(":")
        if len(parts) != 4 or parts[:2] != ["v2", "i"] or parts[2] not in {"t", "e", "n", "x", "w"}:
            await query.answer("Acțiune invalidă", show_alert=True)
            return
        try:
            item_id = uuid.UUID(parts[3])
        except ValueError:
            await query.answer("Acțiune invalidă", show_alert=True)
            return
        detail = await item_detail(
            context.application.bot_data["v2_pool"], config, config.telegram_user_id,
            parts[2], item_id,
        )
        if detail is None:
            await query.answer("Elementul nu mai este disponibil", show_alert=True)
            return
        await query.answer()
        await query.edit_message_text(detail[0], reply_markup=detail[1])

    async def on_new(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        if not query or not update.effective_user or update.effective_user.id != config.telegram_user_id:
            return
        prompt = add_prompt((query.data or "").removeprefix("v2:new:"))
        if not prompt:
            await query.answer("Acțiune invalidă", show_alert=True)
            return
        await query.answer()
        await context.bot.send_message(chat_id=config.telegram_user_id, text=prompt)

    async def on_category_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        if not query or not update.effective_user or update.effective_user.id != config.telegram_user_id:
            return
        parts = (query.data or "").split(":")
        if len(parts) != 4 or parts[:2] != ["v2", "c"]:
            await query.answer("Acțiune invalidă", show_alert=True)
            return
        try:
            expense_id, version = uuid.UUID(parts[2]), int(parts[3])
        except ValueError:
            await query.answer("Acțiune invalidă", show_alert=True)
            return
        menu = await category_menu(
            context.application.bot_data["v2_pool"], config.telegram_user_id, expense_id, version,
        )
        if not menu:
            await query.answer("Cheltuiala a fost modificată între timp", show_alert=True)
            return
        await query.answer()
        await query.edit_message_text(menu[0], reply_markup=menu[1])

    async def on_category_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        if not query or not update.effective_user or update.effective_user.id != config.telegram_user_id:
            return
        parts = (query.data or "").split(":")
        if len(parts) != 5 or parts[:2] != ["v2", "k"]:
            await query.answer("Acțiune invalidă", show_alert=True)
            return
        try:
            expense_id, version = uuid.UUID(parts[2]), int(parts[3])
        except ValueError:
            await query.answer("Acțiune invalidă", show_alert=True)
            return
        message = await change_expense_category(
            context.application.bot_data["v2_pool"], config.telegram_user_id,
            expense_id, version, parts[4],
        )
        if not message:
            await query.answer("Categoria sau cheltuiala s-a schimbat între timp", show_alert=True)
            return
        await query.answer(message)
        await query.edit_message_text(message)

    async def on_quick_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        if not query or not update.effective_user or update.effective_user.id != config.telegram_user_id:
            return
        parts = (query.data or "").split(":")
        if len(parts) not in {5, 6} or parts[:2] != ["v2", "q"]:
            await query.answer("Acțiune invalidă", show_alert=True)
            return
        try:
            item_id = uuid.UUID(parts[3])
        except ValueError:
            await query.answer("Acțiune invalidă", show_alert=True)
            return
        pool = context.application.bot_data["v2_pool"]
        if parts[2] == "a" and len(parts) == 6 and parts[5] in {"yes", "no"}:
            try:
                version = int(parts[4])
            except ValueError:
                await query.answer("Acțiune invalidă", show_alert=True)
                return
            message = await record_class_attendance(
                pool, config, config.telegram_user_id, item_id, version, parts[5] == "yes",
            )
            if not message:
                await query.answer("Cursul s-a schimbat sau încă nu a început", show_alert=True)
                return
            await query.answer(message)
            await query.edit_message_text(message)
            return
        if parts[2] == "n" and len(parts) == 6 and parts[5] in {"read", "archive"}:
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    """UPDATE moodle_posts SET is_read=true,
                    archived_at=CASE WHEN $3::boolean THEN now() ELSE archived_at END
                    WHERE id=$1 AND owner_id=$2 AND archived_at IS NULL AND filtered_out=false
                    AND is_read=false AND substring(content_hash FROM 1 FOR 8)=$4 RETURNING title""",
                    item_id, config.telegram_user_id, parts[5] == "archive", parts[4],
                )
            if not row:
                await query.answer("Noutatea a fost deja modificată", show_alert=True)
                return
            message = f"{'Arhivat' if parts[5] == 'archive' else 'Marcat ca citit'}: {row['title']}"
            await query.answer(message)
            await query.edit_message_text(message)
            return
        if len(parts) != 6 or parts[2] not in {"t", "e"}:
            await query.answer("Acțiune invalidă", show_alert=True)
            return
        try:
            version = int(parts[4])
        except ValueError:
            await query.answer("Acțiune invalidă", show_alert=True)
            return
        now = datetime.now(ZoneInfo(config.timezone))
        if parts[2] == "t" and parts[5] == "tomorrow":
            when = datetime.combine(now.date() + timedelta(days=1), time(9), ZoneInfo(config.timezone))
            command = Command(type="reschedule_task", data={
                "task_id": str(item_id), "due_at": when.isoformat(), "expected_version": version,
            })
        elif parts[2] == "e" and parts[5] == "hour":
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    """SELECT starts_at FROM calendar_entries WHERE id=$1 AND owner_id=$2
                    AND version=$3 AND status='active' AND kind='reminder'""",
                    item_id, config.telegram_user_id, version,
                )
            if not row:
                await query.answer("Reminderul s-a schimbat între timp", show_alert=True)
                return
            when = max(row["starts_at"], now) + timedelta(hours=1)
            command = Command(type="reschedule_entry", data={
                "entry_id": str(item_id), "starts_at": when.isoformat(), "expected_version": version,
            })
        else:
            await query.answer("Acțiune invalidă", show_alert=True)
            return
        result = await execute_command(
            pool, config, config.telegram_user_id, command,
            idempotency_key=f"quick:{item_id}:v{version}:{parts[5]}",
        )
        await query.answer(result.message, show_alert=result.status == "needs_input")
        if result.status in {"saved", "already_done"}:
            await query.edit_message_text(result.message)

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
                    """SELECT starts_at FROM calendar_entries WHERE id=$1 AND owner_id=$2
                    AND version=$3 AND kind='reminder' AND status='active'""",
                    entry_id, config.telegram_user_id, version,
                )
            if not current:
                await query.answer("Reminderul a fost modificat între timp", show_alert=True)
                return
            old_local = current["starts_at"].astimezone(ZoneInfo(config.timezone))
            tomorrow = datetime.combine(
                datetime.now(ZoneInfo(config.timezone)).date() + timedelta(days=1),
                time(old_local.hour, old_local.minute), ZoneInfo(config.timezone),
            )
            command = Command(type="reschedule_entry", data={
                "entry_id": str(entry_id),
                "starts_at": tomorrow.isoformat(),
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
    app.add_handler(CallbackQueryHandler(wrap(on_action_menu), pattern=r"^v2:a:"), group=group)
    app.add_handler(CallbackQueryHandler(wrap(on_item), pattern=r"^v2:i:"), group=group)
    app.add_handler(CallbackQueryHandler(wrap(on_new), pattern=r"^v2:new:"), group=group)
    app.add_handler(CallbackQueryHandler(wrap(on_category_menu), pattern=r"^v2:c:"), group=group)
    app.add_handler(CallbackQueryHandler(wrap(on_category_choice), pattern=r"^v2:k:"), group=group)
    app.add_handler(CallbackQueryHandler(wrap(on_quick_action), pattern=r"^v2:q:"), group=group)
    app.add_handler(CallbackQueryHandler(wrap(on_navigation), pattern=r"^v2:n:"), group=group)
