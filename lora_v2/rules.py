"""High-confidence Romanian capture shortcuts for common daily facts."""

import re
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from lora_v2.agent import Candidate, Interpretation


WEEKDAYS = {
    "luni": 0, "marți": 1, "marti": 1, "miercuri": 2, "joi": 3,
    "vineri": 4, "sâmbătă": 5, "sambata": 5, "duminică": 6, "duminica": 6,
}


def _day(fragment: str, now: datetime) -> datetime | None:
    value = fragment.casefold()
    mentions = list(re.finditer(r"\b(?:poimâine|poimaine|mâine|maine|azi|luni|marți|marti|miercuri|joi|vineri|sâmbătă|sambata|duminică|duminica)\b", value))
    if not mentions:
        return None
    first = mentions[0].group(0)
    if first in {"poimâine", "poimaine"}:
        return now + timedelta(days=2)
    if first in {"mâine", "maine"}:
        return now + timedelta(days=1)
    for name, weekday in WEEKDAYS.items():
        if first == name:
            delta = (weekday - now.weekday()) % 7 or 7
            return now + timedelta(days=delta)
    if first == "azi":
        return now
    return None


def extract_common(text: str, now: datetime, timezone: str) -> tuple[Interpretation, str]:
    """Return grounded actions, a clarification, and text still needing the LLM."""
    local_now = now.astimezone(ZoneInfo(timezone))
    actions: list[Candidate] = []
    questions: list[str] = []
    remaining: list[str] = []
    clauses = [part.strip() for part in re.split(r"(?<=[.!?;])\s+|\n+", text) if part.strip()]
    for clause in clauses:
        source = clause.casefold()
        handled = False
        day = _day(clause, local_now)
        if any(item.type == "create_calendar_entry" and item.kind == "reminder" for item in actions) and re.search(r"dacă nu|daca nu", source) and re.search(r"poimâine|poimaine", source):
            handled = True
        if re.search(r"\b(?:meci|fotbal)\b", source) and day:
            start = re.search(r"\b(?:de la|la ora|începe la|incepe la)\s*(\d{1,2})(?::(\d{2}))?\b", source)
            if start:
                hour, minute = int(start.group(1)), int(start.group(2) or 0)
                if hour < 24 and minute < 60:
                    at = datetime.combine(day.date(), time(hour, minute), ZoneInfo(timezone))
                    actions.append(Candidate(type="create_calendar_entry", kind="event",
                        title="Meci de fotbal", starts_at=at.isoformat(),
                        alert_offsets_minutes=[30, 0], confidence=0.99, evidence=clause))
                    handled = True
        if re.search(r"\b(?:sun|sunat|să sun|sa sun)\b", source) and day:
            target = re.search(r"\b(?:la|de la|ora)\s*(\d{1,2})(?::(\d{2}))?\b", source)
            if "amia" in source and not target:
                subject = re.search(r"\b(?:sun|sunat)\s+(?:la\s+)?([^,.;]+)", clause, re.IGNORECASE)
                title = "Sună " + (subject.group(1).strip() if subject else "persoana menționată")
                title = re.split(r"\s+pe la\s+|\s+dar\s+", title, maxsplit=1)[0]
                at = datetime.combine(day.date(), time(12, 0), ZoneInfo(timezone))
                actions.append(Candidate(type="create_calendar_entry", kind="reminder",
                    title=title[:300], starts_at=at.isoformat(), alert_offsets_minutes=[0],
                    followup_evening="dacă nu" in text.casefold() or "daca nu" in text.casefold(),
                    confidence=0.5, evidence=clause,
                    missing_information="Confirmi ora 12:00 pentru apel?"))
                handled = True
            elif target:
                hour, minute = int(target.group(1)), int(target.group(2) or 0)
                if hour < 24 and minute < 60:
                    subject = re.search(r"\b(?:sun|sunat)\s+(?:la\s+)?([^,.;]+)", clause, re.IGNORECASE)
                    title = "Sună " + (subject.group(1).strip() if subject else "persoana menționată")
                    at = datetime.combine(day.date(), time(hour, minute), ZoneInfo(timezone))
                    actions.append(Candidate(type="create_calendar_entry", kind="reminder",
                        title=title[:300], starts_at=at.isoformat(), alert_offsets_minutes=[0],
                        followup_evening="dacă nu" in source or "daca nu" in source,
                        confidence=0.99, evidence=clause))
                    handled = True
        if not handled and day and re.search(r"\b(?:adu-mi aminte|amintește-mi|aminteste-mi)\b", source):
            target = re.search(r"\b(?:la|ora)\s*(\d{1,2})(?::(\d{2}))?\b", source)
            action = re.search(r"\b(?:să|sa)\s+([^,.;]+)", clause, re.IGNORECASE)
            if target and action:
                hour, minute = int(target.group(1)), int(target.group(2) or 0)
                if hour < 24 and minute < 60:
                    at = datetime.combine(day.date(), time(hour, minute), ZoneInfo(timezone))
                    title = re.sub(r"\s+(?:la|ora)\s+\d{1,2}(?::\d{2})?\s*$", "", action.group(1).strip(), flags=re.IGNORECASE)
                    actions.append(Candidate(type="create_calendar_entry", kind="reminder",
                        title=title[:300], starts_at=at.isoformat(),
                        alert_offsets_minutes=[0], confidence=0.99, evidence=clause))
                    handled = True
        if not handled and day and re.search(r"\b(?:trebuie să|trebuie sa|am de)\b", source):
            target = re.search(r"\b(?:la|ora)\s*(\d{1,2})(?::(\d{2}))?\b", source)
            action = re.search(r"\b(?:trebuie să|trebuie sa|am de)\s+([^,.;]+)", clause, re.IGNORECASE)
            if target and action:
                hour, minute = int(target.group(1)), int(target.group(2) or 0)
                if hour < 24 and minute < 60:
                    at = datetime.combine(day.date(), time(hour, minute), ZoneInfo(timezone))
                    title = action.group(1).strip()
                    title = re.sub(r"^la\s+\d{1,2}(?::\d{2})?\s*", "", title, flags=re.IGNORECASE)
                    title = re.sub(r"\s+p[âa]n[ăa] la\s+\d{1,2}(?::\d{2})?\s*$", "", title, flags=re.IGNORECASE)
                    actions.append(Candidate(type="create_task", title=title[:300],
                        due_at=at.isoformat(), confidence=0.99, evidence=clause))
                    handled = True
        money = re.search(r"\b(\d+(?:[.,]\d{1,2})?)\s*(?:lei|ron)\b", source)
        if money and re.search(r"\b(?:cheltuit|dat|plătit|platit|costat|cumpărat|cumparat|cantin[ăa])\b", source):
            amount = float(money.group(1).replace(",", "."))
            if amount > 0:
                food = bool(re.search(r"\b(?:cantin[ăa]|mâncare|mancare|restaurant|piept de pui|piure)\b", source))
                transport = bool(re.search(r"\b(?:bolt|uber|taxi|transport|autobuz|metrou)\b", source))
                merchant = "Cantină" if re.search(r"\bcantin[ăa]\b", source) else "Bolt" if re.search(r"\bbolt\b", source) else "Uber" if re.search(r"\buber\b", source) else None
                actions.append(Candidate(type="log_expense", amount=amount, currency="RON",
                    category="mâncare" if food else "transport" if transport else None,
                    merchant=merchant,
                    description=clause[:300], spent_at=local_now.isoformat(),
                    confidence=0.99 if food or transport else 0.5, evidence=clause))
                handled = True
                if "piept de pui" in source and ("piure" in source or "pireu" in source):
                    actions.append(Candidate(type="log_meal", description="Piept de pui cu piure",
                        eaten_at=local_now.isoformat(), items=[
                            {"name": "Piept de pui", "grams": 150, "calories": 248, "protein_g": 46, "carbs_g": 0, "fat_g": 5},
                            {"name": "Piure", "grams": 200, "calories": 220, "protein_g": 4, "carbs_g": 35, "fat_g": 8},
                        ], estimate_source="text", confidence=0.9, evidence=clause))
                    questions.append("Am estimat porția de pui la 150 g și piureul la 200 g. Trimite o poză sau corectează gramajele dacă vrei o estimare mai bună.")
        if money and re.search(r"\b(?:primit|încasat|incasat|salariu|venit)\b", source):
            amount = float(money.group(1).replace(",", "."))
            if amount > 0:
                actions.append(Candidate(type="log_income", amount=amount, currency="RON",
                    description=clause[:300], received_at=local_now.isoformat(),
                    confidence=0.95, evidence=clause))
                handled = True
        workout = re.search(r"\b(\d{1,3})\s*(?:de\s+)?minute\b", source)
        if workout and re.search(r"\b(?:sal[ăa]|antrenament|workout)\b", source):
            activity = re.search(r"antrenament(?:ul)?\s+de\s+([^,.;]*?)(?:\s+timp\s+de|\s+\d{1,3}\s*(?:de\s+)?minute|$)", source)
            name = "Antrenament de " + activity.group(1).strip() if activity else "Antrenament"
            actions.append(Candidate(type="log_workout", activity=name,
                duration_minutes=int(workout.group(1)), starts_at=local_now.isoformat(),
                confidence=0.95, evidence=clause))
            handled = True
        if not handled and re.search(r"\b(?:mâncat|mancat)\b", source):
            food_items = re.findall(r"\b(\d{1,4})\s*g\s+([^,.;]+?)(?=\s+și\s+\d{1,4}\s*g\b|\s+si\s+\d{1,4}\s*g\b|$)", clause.rstrip(".!? "), re.IGNORECASE)
            if food_items:
                items = [{"name": name.strip(), "grams": int(grams)} for grams, name in food_items if name.strip()]
                if items:
                    actions.append(Candidate(type="log_meal", eaten_at=local_now.isoformat(),
                        description=", ".join(f"{item['grams']} g {item['name']}" for item in items),
                        items=items, estimate_source="text", confidence=0.6, evidence=clause,
                        missing_information="Sunt gramajele cântărite crude sau după gătire?"))
                    handled = True
        water = re.search(r"\b(\d{2,4})\s*ml\s*(?:de\s+)?ap[ăa]\b", source)
        liters = re.search(r"\b(\d+(?:[.,]\d+)?)\s*(?:l|litri|litru)\s*(?:de\s+)?ap[ăa]\b", source)
        one_liter = re.search(r"\b(?:un|o)\s+litru\s+(?:de\s+)?ap[ăa]\b", source)
        weight = re.search(r"\b(\d{2,3}(?:[.,]\d)?)\s*kg\b", source)
        sleep = re.search(r"\b(?:dormit|somn)\s*(\d{1,2}(?:[.,]\d)?)\s*(?:ore|h)\b", source)
        if water or liters or one_liter or weight or sleep:
            actions.append(Candidate(type="log_health", log_date=(day or local_now).date().isoformat(),
                water_ml_delta=int(water.group(1)) if water else int(float(liters.group(1).replace(",", ".")) * 1000) if liters else 1000 if one_liter else None,
                weight_kg=float(weight.group(1).replace(",", ".")) if weight else None,
                sleep_hours=float(sleep.group(1).replace(",", ".")) if sleep else None,
                confidence=0.95, evidence=clause))
            handled = True
        if not handled:
            remaining.append(clause)
    return Interpretation(actions=actions, reply="\n".join(questions) or None), " ".join(remaining)
