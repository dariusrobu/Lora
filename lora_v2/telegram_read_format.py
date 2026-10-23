"""Readable, Telegram-safe presentation for the v2 read commands."""

import re
from html import escape


_HEADINGS = {
    "today": "☀️ Azi", "tomorrow": "🌤️ Mâine", "calendar": "📅 Calendar",
    "tasks": "✅ Taskuri", "reminders": "⏰ Remindere", "university": "🎓 Facultate",
    "news": "📣 Noutăți", "money": "💳 Bani", "balance": "💰 Sold",
    "expenses": "💸 Cheltuieli", "workout": "🏋️ Antrenamente",
}
_KINDS = {"Eveniment": "📅", "Reminder": "⏰", "Facultate": "🎓"}


def _safe(value: str) -> str:
    # Each line is complete HTML, so it can be omitted without leaving open tags.
    shortened = value[:240] + "…" if len(value) > 240 else value
    return escape(shortened, quote=False)


def _item(line: str) -> str:
    content = line.removeprefix("• ")
    match = re.match(r"^(\d{2}\.\d{2} \d{2}:\d{2}|\d{2}:\d{2})(?: · | )(.+)$", content)
    if match:
        remainder = match.group(2)
        kind = next((name for name in _KINDS if remainder.startswith(name + ": ")), None)
        if kind:
            remainder = f"{_KINDS[kind]} {remainder[len(kind) + 2:]}"
        return f"• <b>{match.group(1)}</b>  {_safe(remainder)}"
    return f"• {_safe(content)}"


def format_read_summary(intent: str, plain_text: str) -> str:
    """Add scan-friendly sections while escaping all data from the plain answer."""
    if intent not in _HEADINGS:
        raise ValueError(f"Unknown read intent: {intent}")
    raw = plain_text.splitlines()
    title = _HEADINGS[intent]
    if intent in {"today", "tomorrow"} and raw and re.fullmatch(r"(?:Azi|Mâine), \d{2}\.\d{2}:", raw[0]):
        title += " · " + raw.pop(0).split(", ", 1)[1].rstrip(":")
    elif raw and (raw[0].endswith(":") or raw[0] in {"Bani:", "Remindere:"}):
        raw.pop(0)

    lines = [f"<b>{title}</b>"]
    if intent in {"today", "tomorrow", "university"}:
        lines.extend(["", "📅 <b>Calendar</b>" if intent != "university" else "📚 <b>Programul de azi</b>"])
    elif intent == "calendar":
        lines.append("Următoarele 7 zile")
    elif intent == "tasks":
        lines.extend(["", "<b>Pe proiecte</b>"])
    elif intent == "news":
        lines.extend(["", "<b>Anunțuri și forumuri necitite</b>"])
    elif intent == "money":
        lines.extend(["", "<b>Privire de ansamblu</b>"])
    elif intent == "expenses":
        lines.extend(["", "<b>Luna aceasta</b>"])
    else:
        lines.append("")

    for line in raw:
        if line == "Taskuri deschise:":
            lines.extend(["", "✅ <b>Taskuri deschise</b>"])
        elif line == "Ultimele cheltuieli:":
            lines.extend(["", "🧾 <b>Ultimele cheltuieli</b>"])
        elif line in {"De verificat:", "Urmează:"}:
            lines.extend(["", f"<b>{_safe(line.rstrip(':'))}</b>"])
        elif intent == "calendar" and re.fullmatch(r"[^:]+ \d{2}\.\d{2}:", line):
            lines.extend(["", f"<b>{_safe(line.rstrip(':'))}</b>"])
        elif intent == "tasks" and line.endswith(":") and not line.startswith("•"):
            lines.extend(["", f"<b>{_safe(line.rstrip(':'))}</b>"])
        elif intent == "news" and line.startswith("• "):
            news = line.removeprefix("• ")
            course, separator, detail = news.partition(" · ")
            if separator:
                lines.append(f"• <b>{_safe(course)}</b> · {_safe(detail)}")
            else:
                lines.append(_item(line))
        elif line.startswith("• "):
            lines.append(_item(line))
        elif line.startswith("Sold estimat:"):
            lines.append("💰 <b>Sold estimat</b>  " + _safe(line.removeprefix("Sold estimat:").strip()))
        elif line.startswith("Cheltuieli luna aceasta:"):
            amount = line.split(":", 1)[1].strip()
            if amount:
                lines.append("💸 <b>Cheltuieli luna aceasta</b>  " + _safe(amount))
        elif line.startswith("Antrenamente săptămâna aceasta:"):
            lines.append("📈 <b>Săptămâna aceasta</b>  " + _safe(line.split(":", 1)[1].strip()))
        elif line.startswith("Ultimul:"):
            lines.extend(["", "<b>Ultimul antrenament</b>", _safe(line.split(":", 1)[1].strip())])
        elif line.startswith("Noutăți necitite:"):
            lines.extend(["", "📣 <b>Noutăți necitite</b>  " + _safe(line.split(":", 1)[1].strip())])
        else:
            lines.append(_safe(line))

    result: list[str] = []
    for line in lines:
        candidate = "\n".join([*result, line])
        if len(candidate) > 3700:
            result.extend(["", "… Restul este în Mini App."])
            break
        result.append(line)
    return "\n".join(result).rstrip()
