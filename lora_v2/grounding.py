"""Deterministic guardrails for dates and amounts extracted by local models."""

import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from lora_v2.agent import Candidate
from lora_v2.config import Settings


WEEKDAYS = {
    "luni": 0, "marți": 1, "marti": 1, "miercuri": 2, "joi": 3,
    "vineri": 4, "sâmbătă": 5, "sambata": 5, "duminică": 6, "duminica": 6,
}


def grounding_issue(candidate: Candidate, text: str, settings: Settings, now: datetime) -> str | None:
    """Reject conspicuous temporal or monetary mismatches before any AI write."""
    if candidate.evidence and candidate.evidence.casefold() in text.casefold():
        source = candidate.evidence.casefold()
    else:
        source = text.casefold()
    local_now = now.astimezone(ZoneInfo(settings.timezone))
    if candidate.type in {"log_expense", "log_income", "log_meal", "log_workout"} and re.search(r"\bazi\b", source):
        timestamp = {
            "log_expense": candidate.spent_at,
            "log_income": candidate.received_at,
            "log_meal": candidate.eaten_at,
            "log_workout": candidate.starts_at,
        }[candidate.type]
        if timestamp:
            try:
                logged_day = datetime.fromisoformat(timestamp).astimezone(ZoneInfo(settings.timezone)).date()
            except ValueError:
                return "Când s-a întâmplat?"
            if logged_day != local_now.date():
                return "Data extrasă nu corespunde cu «azi». Confirmi data?"
    if candidate.type in {"log_expense", "log_income"}:
        amounts = {float(value.replace(",", ".")) for value in re.findall(r"\b(\d+(?:[.,]\d{1,2})?)\s*(?:lei|ron)\b", source)}
        if amounts and candidate.amount not in amounts:
            return "Suma cheltuielii nu corespunde cu mesajul. Cât ai plătit?"
    if candidate.type != "create_calendar_entry":
        return None
    if source == text.casefold() and len(re.findall(
        r"\bmâine\b|\bmaine\b|\bpoimâine\b|\bpoimaine\b|\bduminic[ăa]\b", source
    )) > 1:
        return "Mesajul conține mai multe date. Pe ce zi pun acest eveniment?"
    if "pe la amiaz" in source or "în jurul amie" in source:
        if not (candidate.confidence < 0.85 and candidate.starts_at and
                datetime.fromisoformat(candidate.starts_at).hour == 12):
            return "Pentru reminderul de la amiază, este bună ora 12:00?"
    if not candidate.starts_at:
        return "La ce dată și oră să pun acest element?"
    try:
        starts = datetime.fromisoformat(candidate.starts_at).astimezone(ZoneInfo(settings.timezone))
    except (ValueError, TypeError):
        return "La ce dată și oră să pun acest element?"
    if re.search(r"\bpoimâine\b|\bpoimaine\b", source):
        # A conditional "dacă nu ... poimâine" describes a follow-up, not
        # the primary event. Its day is checked after the user's answer.
        if "dacă" not in source and starts.date() != (local_now + timedelta(days=2)).date():
            return "Data calculată pentru «poimâine» nu corespunde. Ce dată dorești?"
    elif re.search(r"\bmâine\b|\bmaine\b", source):
        if starts.date() != (local_now + timedelta(days=1)).date():
            return "Data calculată pentru «mâine» nu corespunde. Ce dată dorești?"
    else:
        for word, weekday in WEEKDAYS.items():
            if re.search(rf"\b{word}\b", source):
                delta = (weekday - local_now.weekday()) % 7 or 7
                if starts.date() != (local_now + timedelta(days=delta)).date():
                    return f"Data calculată pentru {word} nu corespunde. Confirmi ziua?"
                break
    start_match = re.search(r"\b(?:de la|începe la|incepe la)\s*(\d{1,2})(?::(\d{2}))?\b", source)
    if start_match:
        hour = int(start_match.group(1))
        minute = int(start_match.group(2) or 0)
        if (starts.hour, starts.minute) != (hour, minute):
            return f"Evenimentul pare să înceapă la {hour:02d}:{minute:02d}. Confirmi ora?"
    return None
