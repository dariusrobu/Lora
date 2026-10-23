"""Quick-action menus explain what each Telegram button opens."""

import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from lora_v2.config import Settings
from lora_v2.telegram_quick_actions import action_menu, item_detail


def _settings() -> Settings:
    return Settings(database_url="postgresql://unused", telegram_bot_token="test", telegram_user_id=123)


@pytest.mark.asyncio
async def test_today_picker_names_item_types_and_times() -> None:
    task_id, reminder_id, event_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    local = ZoneInfo("Europe/Bucharest")

    class FakeConnection:
        async def fetch(self, query: str, *_args: object) -> list[dict[str, object]]:
            assert "owner_id=$1" in query
            if "FROM tasks" in query:
                return [{"id": task_id, "title": "Pregătește geanta", "version": 1,
                         "item_kind": "t", "item_at": None}]
            return [
                {"id": reminder_id, "title": "Ia geanta", "version": 1, "item_kind": "e",
                 "entry_kind": "reminder", "item_at": datetime(2026, 10, 23, 19, 30, tzinfo=local)},
                {"id": event_id, "title": "Fotbal", "version": 1, "item_kind": "e",
                 "entry_kind": "event", "item_at": datetime(2026, 10, 23, 20, 0, tzinfo=local)},
            ]

    class FakePool:
        def acquire(self) -> "FakePool":
            return self

        async def __aenter__(self) -> FakeConnection:
            return FakeConnection()

        async def __aexit__(self, *_args: object) -> None:
            return None

    text, keyboard = await action_menu(FakePool(), _settings(), 123, "today")
    labels = [row[0].text for row in keyboard.inline_keyboard]
    assert "Nu se modifică nimic" in text
    assert labels[0].startswith("⏰ Reminder · 19:30 · Ia geanta")
    assert labels[1].startswith("📅 Eveniment · 20:00 · Fotbal")
    assert labels[2].startswith("✅ Task · Pregătește geanta")
    assert labels[3:6] == ["➕ Task pentru azi", "➕ Reminder pentru azi", "➕ Eveniment pentru azi"]
    assert labels[-1] == "↩ Înapoi la rezumat"


@pytest.mark.asyncio
async def test_reminder_detail_explains_each_action() -> None:
    reminder_id = uuid.uuid4()

    class FakeConnection:
        async def fetchrow(self, query: str, *_args: object) -> dict[str, object]:
            assert "owner_id=$2" in query
            return {"title": "Ia geanta", "notes": None, "version": 2,
                    "kind": "reminder", "legacy_source": None,
                    "starts_at": datetime(2026, 10, 23, 19, 30, tzinfo=ZoneInfo("Europe/Bucharest"))}

    class FakePool:
        def acquire(self) -> "FakePool":
            return self

        async def __aenter__(self) -> FakeConnection:
            return FakeConnection()

        async def __aexit__(self, *_args: object) -> None:
            return None

    detail = await item_detail(FakePool(), _settings(), 123, "e", reminder_id)
    assert detail is not None
    text, keyboard = detail
    assert text.startswith("⏰ Reminder\nIa geanta")
    labels = [button.text for row in keyboard.inline_keyboard for button in row]
    assert labels[:3] == ["✅ Am făcut", "⏰ Peste o oră", "📅 Mută pe mâine"]
