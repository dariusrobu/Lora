from datetime import datetime, timedelta
import pytest

from core.agent import _fast_reminder_action
from core.reminder_text import normalize_reminder_text
from lora_v2.rules import extract_common
from zoneinfo import ZoneInfo


def test_relative_reminder_variants():
    cases = [
        ("Adu-mi aminte în 5 minute să beau apă", "beau apă", timedelta(minutes=5)),
        ("Adu-mi aminte peste o oră să sun pe mama", "sun pe mama", timedelta(hours=1)),
        ("Adu-mi aminte peste 2 zile să verific proiectul", "verific proiectul", timedelta(days=2)),
        ("Adu-mi aminte peste 1 săptămână să trimit documentul", "trimit documentul", timedelta(weeks=1)),
    ]
    now = datetime.now()
    for message, title, delta in cases:
        result = _fast_reminder_action(message)
        assert result and result["intent"] == "add_reminder"
        assert result["data"]["title"] == title
        scheduled = datetime.strptime(
            f"{result['data']['event_date']} {result['data']['event_time']}",
            "%Y-%m-%d %H:%M",
        )
        assert abs((scheduled - (now + delta)).total_seconds()) < 90


def test_absolute_time_and_tomorrow_reminders():
    at_time = _fast_reminder_action("Adu-mi aminte la 23:59 să închid laptopul")
    tomorrow = _fast_reminder_action("Adu-mi aminte mâine să merg la bibliotecă")
    assert at_time and at_time["data"]["event_time"] == "23:59"
    assert tomorrow and tomorrow["data"]["title"] == "merg la bibliotecă"


def test_urgent_reminder_is_explicit_and_not_part_of_title():
    result = _fast_reminder_action(
        "Adu-mi aminte urgent mâine la 08:01 să mănânc"
    )
    assert result and result["intent"] == "add_reminder"
    assert result["data"]["title"] == "mănânc"
    assert result["data"]["urgent"] is True


def test_tomorrow_with_explicit_time_preserves_date_and_time():
    result = _fast_reminder_action(
        "Adu-mi aminte mâine la ora 10:12 să beau apă"
    )
    assert result and result["intent"] == "add_reminder"
    assert result["data"]["event_time"] == "10:12"
    assert result["data"]["title"] == "beau apă"
    tomorrow = datetime.now().date() + timedelta(days=1)
    assert result["data"]["event_date"] == tomorrow.isoformat()


def test_explicit_reminder_with_keyboard_separator_keeps_entire_list():
    title = "iau geanta de mancare, caserole, genti, incarcatoare, prosoape si cuptor microunde"
    message = f"vreau sa imi aduci azi la ora 13Ș30 aminte sa {title}"
    result = _fast_reminder_action(message)
    assert result and result["intent"] == "add_reminder"
    assert result["data"]["title"] == title
    assert result["data"]["event_time"] == "13:30"
    assert result["data"]["event_date"] == datetime.now().date().isoformat()
    now = datetime(2026, 10, 16, 10, 56, tzinfo=ZoneInfo("Europe/Bucharest"))
    interpretation, remaining = extract_common(message, now, "Europe/Bucharest")
    assert not remaining
    assert len(interpretation.actions) == 1
    action = interpretation.actions[0]
    assert action.type == "create_calendar_entry" and action.kind == "reminder"
    assert action.title == title
    assert action.starts_at == "2026-10-16T13:30:00+03:00"
    assert action.alert_offsets_minutes == [0]


def test_reminder_normalization_preserves_other_text_and_invalid_times():
    assert normalize_reminder_text("Trebuie să iau geanta, prosoape și încărcătoare") == "Trebuie să iau geanta, prosoape și încărcătoare"
    assert normalize_reminder_text("la ora 25Ș99") == "la ora 25Ș99"


@pytest.mark.asyncio
async def test_packing_reminder_agent_routes_without_model(monkeypatch):
    from core.agent import agent_loop
    captured = []

    async def save_pending(pool, intent, module, data):
        captured.append((intent, module, data))

    async def unexpected_model(*args, **kwargs):
        raise AssertionError("Explicit reminder must not be reclassified by the model")

    monkeypatch.setattr("core.state.set_pending_action", save_pending)
    monkeypatch.setattr("core.gemini.generate_structured_response", unexpected_model)
    result = await agent_loop(None, 123,
        "vreau sa imi aduci azi la ora 13Ș30 aminte sa iau geanta de mancare, caserole, genti, incarcatoare, prosoape si cuptor microunde",
        "", "", "", [])
    assert result[0] == "__CONFIRMATION_REQUIRED__"
    assert len(captured) == 1
    intent, module, data = captured[0]
    assert (intent, module) == ("add_reminder", "events")
    assert data["event_time"] == "13:30"
    assert data["title"] == "iau geanta de mâncare, caserole, genti, incarcatoare, prosoape si cuptor microunde"
