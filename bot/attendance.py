"""Attendance callbacks that preserve the original class reminder."""

from html import escape
from typing import Any

from telegram import CallbackQuery
from telegram.constants import ParseMode

from db.queries.university import log_attendance_by_schedule


async def confirm_attendance(
    query: CallbackQuery, pool: Any, schedule_id: int, attended: bool
) -> None:
    """Save attendance before replacing buttons with a persistent receipt."""
    await log_attendance_by_schedule(pool, schedule_id, attended)
    status = "✅ Prezență salvată" if attended else "❌ Absență salvată"
    message = query.message
    original = getattr(message, "text_html", None)
    if not original:
        original = escape(getattr(message, "text", None) or "")
    # Keep the actual reminder's details even if the schedule was later edited.
    original = original.replace(" începe în 15 minute!", "", 1)
    text = f"{original}\n\n<b>{status}</b>" if original else status
    await query.edit_message_text(
        text, parse_mode=ParseMode.HTML, reply_markup=None
    )
    await query.answer(status)
