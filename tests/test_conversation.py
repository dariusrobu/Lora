import pytest

from core.agent import _select_relevant_tools
from core.gemini import _format_history_for_prompt


def test_conversation_history_keeps_roles_and_order():
    history = [
        {"role": "user", "content": "Mă simt blocat cu proiectul."},
        {"role": "assistant", "content": "Care este următorul pas?"},
        {"role": "user", "content": "Cel de mai devreme: documentația."},
    ]
    formatted = _format_history_for_prompt(history)
    assert "U: Mă simt blocat" in formatted
    assert "A: Care este" in formatted
    assert formatted.index("Mă simt") < formatted.index("documentația")


@pytest.mark.parametrize("message", [
    "ce task-uri am azi?",
    "arată-mi cum stau cu banii",
    "ce am în calendar mâine?",
])
def test_agent_selects_tools_for_personal_context(message: str):
    assert _select_relevant_tools(message)


def test_agent_keeps_general_chat_tool_free():
    # The agent may still use its safety-net prompt, but no domain tool is
    # selected for a plain conversational message.
    assert _select_relevant_tools("mă simt obosit și vreau să vorbesc") is None
