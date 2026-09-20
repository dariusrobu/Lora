"""
Tests for core/router.py — routing logic, read-only vs write intent detection,
and confirmation bypass behavior.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_pool():
    """Returns a minimal mock asyncpg pool."""
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=AsyncMock())
    return pool


# ---------------------------------------------------------------------------
# Unit tests: READ_ONLY_INTENTS set
# ---------------------------------------------------------------------------

def test_read_only_intents_exists():
    """READ_ONLY_INTENTS set must be importable and non-empty."""
    from core.router import READ_ONLY_INTENTS  # type: ignore
    assert isinstance(READ_ONLY_INTENTS, (set, frozenset))
    assert len(READ_ONLY_INTENTS) > 0


def test_read_only_intents_contains_list_tasks():
    from core.router import READ_ONLY_INTENTS  # type: ignore
    assert "list_tasks" in READ_ONLY_INTENTS


def test_read_only_intents_does_not_contain_add_task():
    from core.router import READ_ONLY_INTENTS  # type: ignore
    assert "add_task" not in READ_ONLY_INTENTS


def test_read_only_intents_does_not_contain_delete_task():
    from core.router import READ_ONLY_INTENTS  # type: ignore
    assert "delete_task" not in READ_ONLY_INTENTS


def test_write_confirmation_does_not_depend_on_llm_flag(monkeypatch):
    """A model cannot opt out of confirmation by returning false."""
    import core.router as router  # type: ignore

    monkeypatch.setattr(router, "REQUIRE_CONFIRMATION", True)
    assert router.requires_write_confirmation(
        {"intent": "add_task", "needs_confirmation": False}
    )


def test_read_only_intent_does_not_require_confirmation(monkeypatch):
    import core.router as router  # type: ignore

    monkeypatch.setattr(router, "REQUIRE_CONFIRMATION", True)
    assert not router.requires_write_confirmation({"intent": "list_tasks"})


def test_confirmed_action_bypasses_second_confirmation(monkeypatch):
    import core.router as router  # type: ignore

    monkeypatch.setattr(router, "REQUIRE_CONFIRMATION", True)
    assert not router.requires_write_confirmation(
        {"intent": "add_task", "_confirmed_bypass": True}
    )


# ---------------------------------------------------------------------------
# Unit tests: REQUIRE_CONFIRMATION flag
# ---------------------------------------------------------------------------

def test_require_confirmation_defaults_to_true():
    """Database writes require confirmation unless the deployment opts out explicitly."""
    from core.config import REQUIRE_CONFIRMATION  # type: ignore
    assert REQUIRE_CONFIRMATION is True


# ---------------------------------------------------------------------------
# Unit tests: _select_relevant_tools
# ---------------------------------------------------------------------------

def test_select_relevant_tools_tasks_keyword():
    from core.agent import _select_relevant_tools  # type: ignore
    result = _select_relevant_tools("adauga un task nou")
    assert result is not None
    assert "add_task" in result


def test_select_relevant_tools_finance_keyword():
    from core.agent import _select_relevant_tools  # type: ignore
    result = _select_relevant_tools("am cheltuit 50 lei azi")
    assert result is not None
    assert "finance_log" in result


def test_select_relevant_tools_health_keyword():
    from core.agent import _select_relevant_tools  # type: ignore
    result = _select_relevant_tools("am dormit 7 ore")
    assert result is not None
    assert "health_log" in result


def test_select_relevant_tools_general_chat_returns_none():
    """For pure knowledge questions, dynamic selection should return None → chat mode."""
    from core.agent import _select_relevant_tools  # type: ignore
    result = _select_relevant_tools("ce imi poti zice despre atv uri")
    assert result is None


def test_select_relevant_tools_greeting_returns_none():
    from core.agent import _select_relevant_tools  # type: ignore
    result = _select_relevant_tools("salut cum esti")
    assert result is None


def test_select_relevant_tools_multiple_domains():
    """Message referencing both finance and health should include tools from both groups."""
    from core.agent import _select_relevant_tools  # type: ignore
    result = _select_relevant_tools("am cheltuit pe sala si am facut workout")
    assert result is not None
    assert "finance_log" in result
    assert "workout_log" in result


def test_select_relevant_tools_news_keyword():
    """Message asking for political or economic news should include news tools."""
    from core.agent import _select_relevant_tools  # type: ignore
    result = _select_relevant_tools("ce stiri sunt din politica")
    assert result is not None
    assert "get_news" in result


# ---------------------------------------------------------------------------
# Unit tests: Migration runner
# ---------------------------------------------------------------------------

def test_apply_migrations_function_exists():
    """apply_migrations must be importable from db.connection."""
    from db.connection import apply_migrations  # type: ignore
    assert callable(apply_migrations)


# ---------------------------------------------------------------------------
# Unit tests: get_llm_response alias
# ---------------------------------------------------------------------------

def test_get_llm_response_importable():
    from core.gemini import get_llm_response  # type: ignore
    assert callable(get_llm_response)


def test_get_gemini_response_alias():
    """Legacy alias must point to the same function as get_llm_response."""
    from core.gemini import get_llm_response, get_gemini_response  # type: ignore
    assert get_gemini_response is get_llm_response


# ---------------------------------------------------------------------------
# Unit tests: iCloud create_event is async
# ---------------------------------------------------------------------------

def test_create_event_is_coroutine():
    import inspect
    from core.icloud import create_event  # type: ignore
    assert inspect.iscoroutinefunction(create_event)
