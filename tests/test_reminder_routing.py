from core.router import _coerce_voice_reminder_intent


def test_explicit_romanian_reminder_is_not_calendar_event():
    response = {
        "module": "events",
        "intent": "add_event",
        "data": {"title": "să sun pe mama"},
    }

    _coerce_voice_reminder_intent(response, "Adu-mi aminte să sun pe mama mâine la 13:10")

    assert response["intent"] == "add_reminder"
    assert response.get("clarification_needed") is False or "clarification_needed" not in response


def test_reminder_without_time_requests_clarification():
    response = {
        "module": "events",
        "intent": "add_event",
        "data": {"title": "să cumpăr apă"},
    }

    _coerce_voice_reminder_intent(response, "Amintește-mi să cumpăr apă")

    assert response["intent"] == "add_reminder"
    assert response["clarification_needed"] is True
    assert "Când" in response["clarification_question"]


def test_regular_calendar_event_is_unchanged():
    response = {
        "module": "events",
        "intent": "add_event",
        "data": {"title": "ședință", "event_time": "10:00"},
    }

    _coerce_voice_reminder_intent(response, "Adaugă un eveniment ședință mâine la 10:00")

    assert response["intent"] == "add_event"
