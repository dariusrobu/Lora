from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from bot.attendance import confirm_attendance


@pytest.mark.parametrize("attended,status", [(True, "Prezență"), (False, "Absență")])
async def test_confirmation_preserves_class_details(monkeypatch, attended, status):
    save = AsyncMock()
    monkeypatch.setattr("bot.attendance.log_attendance_by_schedule", save)
    query = SimpleNamespace(
        message=SimpleNamespace(text_html='🔔 <b>Politici de marketing</b> începe în 15 minute!\n📖 Seminar · <code>10:15–11:45</code>\n📍 Sala <b>235</b>'),
        edit_message_text=AsyncMock(), answer=AsyncMock(),
    )
    pool = object()
    await confirm_attendance(query, pool, 23, attended)
    save.assert_awaited_once_with(pool, 23, attended)
    text = query.edit_message_text.call_args.args[0]
    for detail in ('Politici de marketing', 'Seminar', '10:15–11:45', '235', status):
        assert detail in text
    assert 'începe în 15 minute' not in text
    assert query.edit_message_text.call_args.kwargs == {'parse_mode': 'HTML', 'reply_markup': None}


async def test_failed_save_keeps_reminder_unchanged(monkeypatch):
    monkeypatch.setattr('bot.attendance.log_attendance_by_schedule', AsyncMock(side_effect=ValueError('Invalid attendance')))
    query = SimpleNamespace(edit_message_text=AsyncMock(), answer=AsyncMock())
    with pytest.raises(ValueError):
        await confirm_attendance(query, object(), 23, True)
    query.edit_message_text.assert_not_awaited()
    query.answer.assert_not_awaited()


async def test_plain_text_fallback_is_html_safe(monkeypatch):
    monkeypatch.setattr('bot.attendance.log_attendance_by_schedule', AsyncMock())
    query = SimpleNamespace(message=SimpleNamespace(text='Curs A & B <test>\n10:15–11:45 · 235'), edit_message_text=AsyncMock(), answer=AsyncMock())
    await confirm_attendance(query, object(), 23, False)
    assert 'A &amp; B &lt;test&gt;' in query.edit_message_text.call_args.args[0]
