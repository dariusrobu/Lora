"""Telegram read summaries remain readable and safe for HTML parse mode."""

import json

import pytest

from lora_v2.notifications import queue_reply
from lora_v2.telegram_read_format import format_read_summary


@pytest.mark.parametrize(
    ("intent", "plain", "expected"),
    [
        ("today", "Azi, 23.10:\n• 10:00 Facultate: Seminar\n• 19:30 Reminder: Ia geanta\n"
         "Taskuri deschise:\n• Pregătește bagajul · Mutare", "✅ <b>Taskuri deschise</b>"),
        ("calendar", "Calendar · următoarele 7 zile:\nVin 23.10:\n"
         "• 20:00 · Eveniment: Fotbal", "<b>Vin 23.10</b>"),
        ("reminders", "Remindere:\nDe verificat:\n• 22.10 19:00 · Sună\n"
         "Urmează:\n• 24.10 12:00 · Cumpără", "<b>Urmează</b>"),
        ("tasks", "Taskuri pe proiecte:\nFacultate:\n• Tema · 24.10 12:00", "<b>Facultate</b>"),
        ("university", "Facultate azi:\n• 10:00 Seminar\nNoutăți necitite: 2.",
         "📣 <b>Noutăți necitite</b>"),
        ("news", "Noutăți necitite de la facultate:\n• Economie · Anunț: Seminar",
         "<b>Economie</b> · Anunț: Seminar"),
        ("money", "Bani:\nSold estimat: încă nesetat.\nCheltuieli luna aceasta: 28.76 RON\n"
         "Ultimele cheltuieli:\n• 20 RON · mâncare", "💰 <b>Sold estimat</b>"),
        ("expenses", "Sold estimat: 200 RON.\nCheltuieli luna aceasta:\n"
         "• mâncare: 15 RON", "<b>Luna aceasta</b>"),
        ("workout", "Antrenamente săptămâna aceasta: 1.\n"
         "Ultimul: 23.10 12:00 · piept · 45 min.", "<b>Ultimul antrenament</b>"),
    ],
)
def test_read_summary_has_sections(intent: str, plain: str, expected: str) -> None:
    formatted = format_read_summary(intent, plain)
    assert expected in formatted
    assert "\n\n" in formatted
    assert len(formatted) < 4000


def test_read_summary_escapes_user_titles_and_truncates_safely() -> None:
    plain = "Taskuri pe proiecte:\nProiect <&>:\n" + "\n".join(
        f"• Task <&> {index} " + "x" * 300 for index in range(30)
    )
    formatted = format_read_summary("tasks", plain)
    assert "<b>Proiect &lt;&amp;&gt;</b>" in formatted
    assert "Task &lt;&amp;&gt;" in formatted
    assert "Restul este în Mini App" in formatted
    assert len(formatted) < 4000
    assert formatted.count("<b>") == formatted.count("</b>")


@pytest.mark.asyncio
async def test_formatted_reply_keeps_html_mode_and_navigation() -> None:
    class FakePool:
        def __init__(self) -> None:
            self.payloads: list[dict[str, object]] = []

        async def execute(self, _query: str, *_args: object) -> None:
            self.payloads.append(json.loads(str(_args[-1])))

    pool = FakePool()
    await queue_reply(pool, 123, "read-1", "<b>Azi</b>", navigation="today", parse_mode="HTML")
    assert pool.payloads == [{
        "text": "<b>Azi</b>", "navigation": "today", "mini_app_url": "", "parse_mode": "HTML",
    }]
