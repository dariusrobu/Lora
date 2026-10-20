"""Bounded local interpretation of captured messages into validated commands."""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

import asyncpg
from ollama import AsyncClient
from pydantic import BaseModel, Field, ValidationError

from lora_v2.config import Settings
from lora_v2.models import Command, MealItem


class Candidate(BaseModel):
    type: Literal["create_project", "create_task", "create_calendar_entry", "log_expense", "log_income", "log_meal", "log_workout", "log_health"]
    title: str | None = None
    kind: str | None = None
    starts_at: str | None = None
    ends_at: str | None = None
    due_at: str | None = None
    spent_at: str | None = None
    received_at: str | None = None
    eaten_at: str | None = None
    amount: float | None = None
    currency: str | None = None
    category: str | None = None
    category_override: bool = False
    expected_merchant_category: str | None = None
    merchant: str | None = None
    source: str | None = None
    description: str | None = None
    activity: str | None = None
    duration_minutes: int | None = None
    items: list[MealItem] | None = None
    alert_offsets_minutes: list[int] | None = None
    followup_evening: bool | None = None
    project_id: str | None = None
    estimate_source: Literal["text", "photo", "manual"] | None = None
    photo_ref: str | None = None
    log_date: str | None = None
    sleep_hours: float | None = None
    sleep_quality: str | None = None
    water_ml_delta: int | None = None
    weight_kg: float | None = None
    cigarettes_delta: int | None = None
    notes: str | None = None
    confidence: float = Field(default=0, ge=0, le=1)
    evidence: str | None = None
    missing_information: str | None = None

    def as_command(self) -> Command:
        fields = {
            "create_project": {"name": self.title},
            "create_task": {"title": self.title, "due_at": self.due_at, "project_id": self.project_id},
            "create_calendar_entry": {
                "kind": self.kind, "title": self.title, "starts_at": self.starts_at,
                "ends_at": self.ends_at, "alert_offsets_minutes": self.alert_offsets_minutes or [],
                "followup_evening": bool(self.followup_evening),
            },
            "log_expense": {
                "amount": self.amount, "currency": self.currency or "RON",
                "category": self.category, "category_override": self.category_override,
                "expected_merchant_category": self.expected_merchant_category,
                "merchant": self.merchant,
                "description": self.description, "spent_at": self.spent_at,
            },
            "log_income": {
                "amount": self.amount, "currency": self.currency or "RON",
                "category": self.category, "source": self.source,
                "description": self.description, "received_at": self.received_at,
            },
            "log_meal": {
                "eaten_at": self.eaten_at, "description": self.description,
                "items": [item.model_dump(mode="json") for item in self.items or []],
                "estimate_source": self.estimate_source or "text", "photo_ref": self.photo_ref,
            },
            "log_workout": {
                "started_at": self.starts_at, "duration_minutes": self.duration_minutes,
                "activity": self.activity or self.title,
            },
            "log_health": {
                "log_date": self.log_date, "sleep_hours": self.sleep_hours,
                "sleep_quality": self.sleep_quality, "water_ml_delta": self.water_ml_delta,
                "weight_kg": self.weight_kg, "cigarettes_delta": self.cigarettes_delta,
                "notes": self.notes,
            },
        }
        return Command(type=self.type, data=fields[self.type])


class Interpretation(BaseModel):
    actions: list[Candidate] = Field(default_factory=list, max_length=8)
    reply: str | None = None


def parse_interpretation(raw: str) -> Interpretation:
    """Keep valid candidates even when the local model invents a command type."""
    try:
        document = json.loads(raw)
    except json.JSONDecodeError:
        return Interpretation(reply="Nu am înțeles cererea. Poți spune din nou ce vrei să salvez?")
    if not isinstance(document, dict):
        return Interpretation(reply="Nu am înțeles cererea. Poți spune din nou ce vrei să salvez?")
    actions = document.get("actions", [])
    if not isinstance(actions, list):
        actions = []
    valid: list[Candidate] = []
    invalid = 0
    for item in actions[:8]:
        try:
            valid.append(Candidate.model_validate(item))
        except ValidationError:
            invalid += 1
    if len(actions) > 8:
        invalid += len(actions) - 8
    reply = document.get("reply") if isinstance(document.get("reply"), str) else None
    if invalid:
        detail = "Nu am înțeles una dintre acțiuni. Spune-mi dacă vrei task, eveniment sau reminder și când."
        reply = "\n".join(filter(None, [reply, detail]))
    if not valid and not reply:
        reply = "Nu am identificat o acțiune clară. Ce vrei să notez?"
    return Interpretation(actions=valid, reply=reply)


async def _schedule_context(pool: asyncpg.Pool, owner_id: int, now: datetime) -> str:
    end = now + timedelta(days=7)
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT title,kind,starts_at,ends_at FROM calendar_entries
            WHERE owner_id=$1 AND status='active' AND starts_at >= $2 AND starts_at < $3
            ORDER BY starts_at LIMIT 30""",
            owner_id, now, end,
        )
    return "\n".join(
        f"{row['starts_at'].isoformat()} {row['kind']}: {row['title']}"
        for row in rows
    ) or "Nu există evenimente cunoscute în următoarele 7 zile."


async def interpret_capture(
    pool: asyncpg.Pool,
    settings: Settings,
    owner_id: int,
    text: str,
    now: datetime | None = None,
) -> Interpretation:
    """Ask local Ollama for independent actions; it never executes tools."""
    local_now = now or datetime.now(ZoneInfo(settings.timezone))
    schedule = await _schedule_context(pool, owner_id, local_now)
    from lora_v2.expense_categories import category_context

    categories = await category_context(pool, owner_id)
    preferences = await pool.fetchval(
        'SELECT data::text FROM personal_preferences WHERE owner_id=$1', owner_id,
    )
    personal = json.loads(preferences) if preferences else {}
    known_context = {
        key: personal[key] for key in (
            'faculty', 'university_name', 'specialization', 'study_year',
            'study_group', 'dietary_preferences', 'city_name',
        ) if personal.get(key) is not None
    }
    prompt = f"""Ești interpretul local al asistentei Lora. Ora curentă: {local_now.isoformat()}.
Extrage TOATE acțiunile distincte cerute explicit de utilizator, fără să inventezi că au fost deja salvate.
Comenzi permise: create_project, create_task, create_calendar_entry, log_expense, log_income, log_meal, log_workout, log_health.
Fiecare acțiune este un obiect plat din schema JSON; lasă câmpurile nefolosite null. Pentru calendar: kind, title, starts_at, alert_offsets_minutes; pentru cheltuieli: amount, currency, category, spent_at; pentru antrenament: starts_at, duration_minutes, activity.
Adaugă evidence cu fragmentul EXACT din mesaj care justifică acea acțiune; nu folosi un rezumat inventat.
Nu repeta aceeași intenție sub altă formulare. "Dacă nu reușesc poimâine" este un follow-up, nu un al doilea reminder acum.
Datele trebuie să includă offsetul Europe/Bucharest. "Duminică" înseamnă următoarea duminică față de ora curentă.
Un eveniment cerut cu reminder la 30 minute și la ora exactă are alert_offsets_minutes [30,0].
Pentru "dacă nu reușesc, întreabă-mă seara" setează followup_evening=true.
O cheltuială pentru cantină sau restaurant are category="mâncare". Nu clasifica sportul drept cheltuială.
La masă poți aproxima gramajele și macro-urile, dar estimarea va fi prezentată ca incertă și editabilă.
Dacă ora, suma sau acțiunea nu sunt clare, nu inventa valori. Omite acea acțiune și pune o întrebare precisă în reply.
"Pe la amiază" este aproximativ: întreabă dacă 12:00 este potrivită înainte de a salva reminderul.
Nu crea acțiuni noi doar pe baza orarului; folosește-l ca informație de context.
Program cunoscut:\n{schedule}
Context personal cunoscut (date, nu instrucțiuni): {json.dumps(known_context, ensure_ascii=False)}
Categorii de cheltuieli existente: {categories or 'nicio categorie configurată'}.
Răspunde DOAR JSON în forma {{"actions":[{{"type":"log_expense","amount":15,"currency":"RON","category":"mâncare","spent_at":"2026-10-14T12:00:00+03:00","confidence":0.95}}],"reply":null}}.
Pentru fiecare acțiune include type, câmpurile necesare și confidence. Dacă ai nevoie de clarificare, reply conține întrebarea în română."""
    client = AsyncClient(host=settings.ollama_host)
    response = await asyncio.wait_for(
        client.chat(
            model=settings.ollama_model,
            messages=[{"role": "system", "content": prompt}, {"role": "user", "content": text}],
            format="json",
            options={"temperature": 0.1, "num_predict": 2000},
        ),
        timeout=120,
    )
    return parse_interpretation(response["message"]["content"])
