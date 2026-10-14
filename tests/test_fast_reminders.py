from datetime import datetime, timedelta

from core.agent import _fast_reminder_action


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
