"""Bounded daily planning over owner-scoped read tools and approved v2 commands."""

import asyncio
import json
import logging
import re
import unicodedata
import uuid
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Literal
from zoneinfo import ZoneInfo

import asyncpg
import httpx
from ollama import AsyncClient
from pydantic import BaseModel, Field

from lora_v2.config import Settings
from lora_v2.models import ActionResult, Command

logger = logging.getLogger(__name__)

ToolName = Literal["agenda", "tasks", "routine"]
Mode = Literal["morning", "evening", "on_demand"]


class ToolChoice(BaseModel):
    tools: list[ToolName] = Field(default_factory=list, max_length=3)


class PlanChoice(BaseModel):
    priority_ids: list[str] = Field(default_factory=list, max_length=3)


def planning_date(text: str, now: datetime) -> date | None:
    """Recognize explicit requests for a daily plan without hijacking normal writes."""
    plain = re.sub(r"\s+", " ", text.casefold().strip())
    normalized = plain.translate(str.maketrans("ăâîșşțţ", "aaisstt"))
    if not re.search(r"\b(organizeaza|planifica|planul|cum imi organizez)\b", normalized):
        return None
    if not re.search(r"\b(ziua|zi|programul|maine|azi)\b", normalized):
        return None
    return now.date() + timedelta(days=1 if "maine" in normalized else 0)


async def _agenda(pool: asyncpg.Pool, owner_id: int, start: datetime, end: datetime) -> list[dict[str, Any]]:
    rows = await pool.fetch(
        """SELECT id,kind,title,starts_at,ends_at,notes,version FROM calendar_entries
        WHERE owner_id=$1 AND status='active' AND starts_at<$3
        AND COALESCE(ends_at,starts_at+interval '15 minutes')>$2
        ORDER BY starts_at LIMIT 80""", owner_id, start, end,
    )
    return [{**dict(row), "id": str(row["id"]), "starts_at": row["starts_at"].isoformat(),
             "ends_at": row["ends_at"].isoformat() if row["ends_at"] else None} for row in rows]


async def _tasks(pool: asyncpg.Pool, owner_id: int, end: datetime) -> list[dict[str, Any]]:
    rows = await pool.fetch(
        """SELECT t.id,t.title,t.due_at,t.version,p.name AS project_name FROM tasks t
        LEFT JOIN projects p ON p.id=t.project_id
        WHERE t.owner_id=$1 AND t.status='pending' AND (t.due_at<$2 OR t.due_at IS NULL)
        ORDER BY t.due_at NULLS LAST,t.created_at LIMIT 40""", owner_id, end,
    )
    return [{**dict(row), "id": str(row["id"]),
             "due_at": row["due_at"].isoformat() if row["due_at"] else None} for row in rows]


async def _routine(pool: asyncpg.Pool, owner_id: int, day: date) -> dict[str, str | None]:
    row = await pool.fetchrow("SELECT data FROM personal_preferences WHERE owner_id=$1", owner_id)
    raw = row["data"] if row else {}
    profile = json.loads(raw) if isinstance(raw, str) else raw
    plan = await pool.fetchrow(
        """SELECT wake_time,itinerary FROM day_plans_v2 WHERE owner_id=$1 AND plan_date=$2
        AND deleted_at IS NULL""", owner_id, day,
    )
    return {"wake_time": str(plan["wake_time"]) if plan and plan["wake_time"] else None,
            "itinerary": str(plan["itinerary"]) if plan and plan["itinerary"] else None,
            "morning_time": str(profile.get("morning_time")) if profile.get("morning_time") else None,
            "eod_time": str(profile.get("eod_time")) if profile.get("eod_time") else None,
            "city_name": str(profile.get("city_name")) if profile.get("city_name") else None,
            "latitude": str(profile.get("latitude")) if profile.get("latitude") is not None else None,
            "longitude": str(profile.get("longitude")) if profile.get("longitude") is not None else None}


def _local_time(value: str | None, fallback: time) -> time:
    try:
        return time.fromisoformat(value[:8]) if value else fallback
    except ValueError:
        return fallback


def brief_due_at(mode: Literal["morning", "evening"], day: date,
                 routine: dict[str, str | None], timezone_name: str) -> datetime:
    zone = ZoneInfo(timezone_name)
    field = "morning_time" if mode == "morning" else "eod_time"
    fallback = time(8) if mode == "morning" else time(20)
    configured = routine.get(field)
    if configured:
        return datetime.combine(day, _local_time(configured, fallback), zone)
    if mode == "morning" and routine.get("wake_time"):
        wake = _local_time(routine["wake_time"], time(7, 30))
        return datetime.combine(day, wake, zone) + timedelta(minutes=30)
    return datetime.combine(day, fallback, zone)


async def _choose_tools(settings: Settings, request_text: str) -> tuple[list[ToolName], bool]:
    """Model can request bounded read tools; daily essentials remain mandatory."""
    try:
        response = await asyncio.wait_for(AsyncClient(host=settings.ollama_host).chat(
            model=settings.ollama_model,
            messages=[{"role": "system", "content":
                       "Alege doar instrumentele de CITIRE necesare pentru planul zilei: agenda, tasks, routine. "
                       "Răspunde JSON: {\"tools\":[\"agenda\",\"tasks\",\"routine\"]}. "
                       "Nu cere modificări și nu inventa alte instrumente."},
                      {"role": "user", "content": request_text}],
            format="json", options={"temperature": 0, "num_predict": 80},
        ), timeout=4)
        selected = ToolChoice.model_validate_json(response["message"]["content"]).tools
        return list(dict.fromkeys(["agenda", "tasks", *selected]))[:3], False
    except (Exception, asyncio.CancelledError) as exc:
        if isinstance(exc, asyncio.CancelledError):
            raise
        logger.info("Daily agent tool choice fallback: %s", type(exc).__name__)
        return ["agenda", "tasks", "routine"], True


async def _unfinished_today(pool: asyncpg.Pool, owner_id: int, current: datetime,
                            zone: ZoneInfo) -> list[dict[str, Any]]:
    start = datetime.combine(current.astimezone(zone).date(), time.min, zone)
    rows = await pool.fetch(
        """SELECT id,title,starts_at FROM calendar_entries WHERE owner_id=$1
        AND kind='reminder' AND status='active' AND starts_at>=$2 AND starts_at<$3
        ORDER BY starts_at LIMIT 10""", owner_id, start, current,
    )
    return [{"id": str(row["id"]), "title": row["title"],
             "starts_at": row["starts_at"].isoformat()} for row in rows]


async def _unconfirmed_yesterday(pool: asyncpg.Pool, owner_id: int,
                                 day: date, zone: ZoneInfo) -> list[str]:
    start = datetime.combine(day - timedelta(days=1), time.min, zone)
    end = datetime.combine(day, time.min, zone)
    rows = await pool.fetch(
        """SELECT title FROM calendar_entries WHERE owner_id=$1 AND kind='reminder'
        AND status='active' AND starts_at >= $2 AND starts_at < $3
        ORDER BY starts_at LIMIT 3""", owner_id, start, end,
    )
    return [str(row["title"]) for row in rows]


async def _weather_note(settings: Settings, routine: dict[str, str | None],
                        day: date, zone: ZoneInfo) -> str | None:
    """Show only actionable forecast conditions; unavailable weather stays absent."""
    if not settings.openweather_api_key:
        return None
    params: dict[str, str | int | float] = {
        "appid": settings.openweather_api_key, "units": "metric", "cnt": 16,
    }
    if routine.get("latitude") and routine.get("longitude"):
        try:
            params["lat"] = float(routine["latitude"] or "")
            params["lon"] = float(routine["longitude"] or "")
        except ValueError:
            return None
    elif routine.get("city_name"):
        params["q"] = routine["city_name"] or ""
    else:
        return None
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get("https://api.openweathermap.org/data/2.5/forecast", params=params)
            response.raise_for_status()
        forecast = [item for item in response.json().get("list", [])
                    if datetime.fromtimestamp(item["dt"], zone).date() == day]
        if not forecast:
            return None
        condition_ids = [int(weather["id"]) for item in forecast
                         for weather in item.get("weather", []) if "id" in weather]
        if any(200 <= condition < 700 for condition in condition_ids):
            return "Se anunță ploaie sau ninsoare; verifică vremea înainte să pleci."
        temperatures = [float(item["main"]["temp"]) for item in forecast if "temp" in item.get("main", {})]
        if temperatures and min(temperatures) < 0:
            return "Sunt prognozate temperaturi sub 0°C; pregătește haine potrivite."
        if temperatures and max(temperatures) >= 32:
            return "Se anunță peste 32°C; ia apă când pleci."
        return None
    except (httpx.HTTPError, KeyError, TypeError, ValueError, OverflowError) as exc:
        logger.info("Morning weather unavailable: %s", type(exc).__name__)
        return None


def _free_slots(entries: list[dict[str, Any]], day: date, zone: ZoneInfo) -> list[str]:
    cursor = datetime.combine(day, time(8), zone)
    limit = datetime.combine(day, time(22), zone)
    occupied = sorted((datetime.fromisoformat(item["starts_at"]).astimezone(zone),
                       datetime.fromisoformat(item["ends_at"]).astimezone(zone)
                       if item["ends_at"] else datetime.fromisoformat(item["starts_at"]).astimezone(zone)
                       + timedelta(minutes=15)) for item in entries)
    slots: list[str] = []
    for begins, ends in [*occupied, (limit, limit)]:
        if begins - cursor >= timedelta(hours=1) and len(slots) < 2:
            slots.append(f"{cursor:%H:%M}–{min(begins, cursor + timedelta(hours=2)):%H:%M}")
        cursor = max(cursor, ends)
    return slots


def _candidates(context: dict[str, Any], day: date, now: datetime,
                zone: ZoneInfo) -> list[tuple[str, Command, str]]:
    entries = context["agenda"]
    classes = [entry for entry in entries if entry["kind"] == "academic" and entry["ends_at"]]
    proposed: list[tuple[str, Command, str]] = []
    for entry in entries:
        if entry["kind"] != "reminder":
            continue
        start = datetime.fromisoformat(entry["starts_at"])
        conflict = next((item for item in classes if
                         datetime.fromisoformat(item["starts_at"]) <= start
                         < datetime.fromisoformat(item["ends_at"])), None)
        if not conflict:
            continue
        suggestion = datetime.fromisoformat(conflict["ends_at"]) + timedelta(minutes=15)
        if suggestion.date() != day or suggestion <= now:
            continue
        command = Command(type="reschedule_entry", data={
            "entry_id": entry["id"], "starts_at": suggestion.isoformat(),
            "expected_version": entry["version"],
        })
        key = f"reminder:{entry['id']}:v{entry['version']}"
        reason = f"«{entry['title']}» se suprapune cu «{conflict['title']}». Îl mut la {suggestion.astimezone(zone):%H:%M}?"
        proposed.append((key, command, reason))
    for task in context["tasks"]:
        if not task["due_at"]:
            continue
        due = datetime.fromisoformat(task["due_at"]).astimezone(zone)
        if due >= now:
            continue
        proposed_day = max(day, now.date() + timedelta(days=1))
        suggestion = datetime.combine(proposed_day, time(9), zone)
        command = Command(type="reschedule_task", data={
            "task_id": task["id"], "due_at": suggestion.isoformat(),
            "expected_version": task["version"],
        })
        key = f"task:{task['id']}:v{task['version']}"
        reason = f"Taskul «{task['title']}» are termen depășit. Îi mut termenul pe {suggestion:%d.%m} la 09:00?"
        proposed.append((key, command, reason))
    return proposed[:8]


async def _choose_priorities(settings: Settings, context: dict[str, Any],
                             candidates: list[tuple[str, Command, str]]) -> tuple[list[str], bool]:
    if not candidates:
        return [], False
    choices = [{"id": key, "reason": reason} for key, _, reason in candidates]
    try:
        response = await asyncio.wait_for(AsyncClient(host=settings.ollama_host).chat(
            model=settings.ollama_model,
            messages=[{"role": "system", "content":
                       "Alege cel mult trei ID-uri de propuneri utile din lista primită. "
                       "Nu inventa ID-uri. Răspunde numai JSON: {\"priority_ids\":[...]}."},
                      {"role": "user", "content": json.dumps({
                          "agenda": context["agenda"], "tasks": context["tasks"],
                          "candidates": choices,
                      }, ensure_ascii=False)}],
            format="json", options={"temperature": 0, "num_predict": 140},
        ), timeout=20)
        ids = PlanChoice.model_validate_json(response["message"]["content"]).priority_ids
        valid = {item[0] for item in candidates}
        return [item for item in dict.fromkeys(ids) if item in valid][:3], False
    except (Exception, asyncio.CancelledError) as exc:
        if isinstance(exc, asyncio.CancelledError):
            raise
        logger.info("Daily agent priority fallback: %s", type(exc).__name__)
        return [item[0] for item in candidates[:3]], True


def _summary(context: dict[str, Any], day: date, mode: Mode, zone: ZoneInfo,
             selected_count: int) -> str:
    if mode == "morning":
        return _morning_summary(context, day, zone, selected_count)
    heading = ("Bună dimineața" if mode == "morning" else
               "Încheiem ziua · mâine" if mode == "evening" else "Planul zilei")
    lines = [f"{heading} · {day:%d.%m}"]
    entries = context["agenda"]
    if entries:
        lines.append("În calendar:")
        lines.extend(f"• {datetime.fromisoformat(item['starts_at']).astimezone(zone):%H:%M} {item['title']}"
                     for item in entries[:8])
        if len(entries) > 8:
            lines.append(f"• încă {len(entries) - 8} elemente în Mini App")
    else:
        lines.append("Calendarul este liber.")
    tasks = context["tasks"]
    if tasks:
        lines.append(f"Taskuri deschise: {len(tasks)}.")
        lines.extend(f"• {item['title']}" for item in tasks[:3])
    else:
        lines.append("Nu ai taskuri restante sau cu termen apropiat.")
    if mode == "evening":
        unfinished = context.get("unfinished_today", [])
        if unfinished:
            lines.append("Remindere de azi rămase deschise:")
            lines.extend(f"• {item['title']}" for item in unfinished[:3])
        lines.append("Verifică ce ai încheiat azi; pentru restul poți alege propunerile de mai jos.")
    elif context.get("free_slots"):
        lines.append("Intervale libere orientative: " + ", ".join(context["free_slots"]) + ".")
    if selected_count:
        lines.append(f"Am {selected_count} {('propunere' if selected_count == 1 else 'propuneri')} pentru tine. Alegi separat pentru fiecare.")
    else:
        lines.append("Nu văd nimic urgent de schimbat.")
    if context.get("model_fallback"):
        lines.append("Ollama nu a răspuns complet; rezumatul și sugestiile de mai sus sunt calculate din datele salvate.")
    return "\n".join(lines)


def _morning_summary(context: dict[str, Any], day: date, zone: ZoneInfo,
                     selected_count: int) -> str:
    """A short, factual plan followed by the complete recorded daily agenda."""
    agenda = context["agenda"]
    tasks = context["tasks"]
    lines = [f"☀️ Bună dimineața · {day:%d.%m}", "", "Planul zilei"]
    due_tasks = [task for task in tasks if task["due_at"] and
                 datetime.fromisoformat(task["due_at"]).astimezone(zone).date() <= day]
    priorities = due_tasks[:3]
    for index, task in enumerate(priorities, 1):
        due_day = datetime.fromisoformat(task["due_at"]).astimezone(zone).date()
        label = "restant" if due_day < day else "termen azi"
        lines.append(f"{index}. {task['title']} ({label})")
    if not priorities:
        next_item = next((entry for entry in agenda if entry["kind"] != "academic"),
                         agenda[0] if agenda else None)
        if next_item:
            start = datetime.fromisoformat(next_item["starts_at"]).astimezone(zone)
            lines.append(f"1. {next_item['title']} la {start:%H:%M}")
        else:
            lines.append("Nu ai termene sau activități înregistrate azi.")

    itinerary = (context.get("routine") or {}).get("itinerary")
    if itinerary:
        lines.append(f"Plan salvat: {itinerary.strip()}")
    if context.get("free_slots") and due_tasks:
        lines.append("Timp liber orientativ: " + ", ".join(context["free_slots"]) + ".")

    lines.extend(["", "Programul de azi"])
    if not agenda:
        lines.append("Nu ai nimic în calendar.")
    for entry in agenda:
        start = datetime.fromisoformat(entry["starts_at"]).astimezone(zone)
        end = (datetime.fromisoformat(entry["ends_at"]).astimezone(zone)
               if entry["ends_at"] else None)
        hours = f"{start:%H:%M}–{end:%H:%M}" if end else f"{start:%H:%M}"
        kind = {"academic": "Facultate", "reminder": "Reminder", "event": "Eveniment"}[entry["kind"]]
        room = f", sala {entry['notes']}" if entry["kind"] == "academic" and entry.get("notes") else ""
        lines.append(f"• {hours} · {kind}: {entry['title']}{room}")

    attention: list[str] = []
    classes = [entry for entry in agenda if entry["kind"] == "academic" and entry["ends_at"]]
    for reminder in (entry for entry in agenda if entry["kind"] == "reminder"):
        start = datetime.fromisoformat(reminder["starts_at"])
        if any(datetime.fromisoformat(lesson["starts_at"]) <= start
               < datetime.fromisoformat(lesson["ends_at"]) for lesson in classes):
            attention.append(f"«{reminder['title']}» se suprapune cu facultatea.")
    overdue = sum(datetime.fromisoformat(task["due_at"]).astimezone(zone).date() < day
                  for task in due_tasks)
    if overdue:
        attention.append(f"{overdue} task{'uri' if overdue != 1 else ''} cu termen depășit.")
    for title in context.get("unconfirmed_yesterday", [])[:2]:
        attention.append(f"Reminder de ieri nemarcat gata: {title}.")
    if attention:
        lines.extend(["", "De urmărit", *(f"• {item}" for item in attention[:4])])

    preparation: list[str] = []
    sport_terms = ("sală", "sala", "antrenament", "fotbal", "alerg", "sport")
    for entry in agenda:
        if entry["kind"] == "event" and any(term in entry["title"].casefold() for term in sport_terms):
            start = datetime.fromisoformat(entry["starts_at"]).astimezone(zone)
            preparation.append(f"Sport planificat: {entry['title']} la {start:%H:%M}.")
    if context.get("weather_note"):
        preparation.append(context["weather_note"])
    if preparation:
        lines.extend(["", "Pregătire", *(f"• {item}" for item in preparation[:3])])
    if selected_count:
        lines.extend(["", "Am o propunere concretă. O primești separat și alegi dacă o aplic."])
    return "\n".join(lines)


async def create_brief(pool: asyncpg.Pool, settings: Settings, owner_id: int,
                       target_date: date, mode: Mode, dedupe_key: str,
                       request_text: str = "", now: datetime | None = None) -> dict[str, Any]:
    """Persist one plan and independent proposals; never execute a write suggestion."""
    current = now or datetime.now(ZoneInfo(settings.timezone))
    zone = ZoneInfo(settings.timezone)
    brief_id = uuid.uuid4()
    row = await pool.fetchrow(
        """INSERT INTO agent_briefs(id,owner_id,target_date,mode,dedupe_key)
        VALUES ($1,$2,$3,$4,$5) ON CONFLICT(owner_id,dedupe_key) DO NOTHING
        RETURNING id""", brief_id, owner_id, target_date, mode, dedupe_key,
    )
    if not row:
        reclaimed = await pool.fetchrow(
            """UPDATE agent_briefs SET status='processing',error_code=NULL,updated_at=now()
            WHERE owner_id=$1 AND dedupe_key=$2 AND
            (status='failed' OR (status='processing' AND updated_at<now()-interval '2 minutes'))
            RETURNING id""", owner_id, dedupe_key,
        )
        if reclaimed:
            brief_id = reclaimed["id"]
        else:
            existing = await pool.fetchrow(
                "SELECT * FROM agent_briefs WHERE owner_id=$1 AND dedupe_key=$2", owner_id, dedupe_key,
            )
            return dict(existing)
    start = datetime.combine(target_date, time.min, zone)
    end = datetime.combine(target_date + timedelta(days=1), time.min, zone)
    tool_events: list[dict[str, Any]] = []
    context: dict[str, Any] = {}
    try:
        selected, tool_fallback = await _choose_tools(settings, request_text or f"Planifică {target_date}")
        tool_events.append({"tool": "selection", "fallback": tool_fallback})
        for name in selected:
            if name == "agenda":
                context[name] = await _agenda(pool, owner_id, start, end)
            elif name == "tasks":
                context[name] = await _tasks(pool, owner_id, end)
            else:
                context[name] = await _routine(pool, owner_id, target_date)
            tool_events.append({"tool": name, "rows": len(context[name])})
        context.setdefault("agenda", [])
        context.setdefault("tasks", [])
        context["free_slots"] = _free_slots(context["agenda"], target_date, zone)
        if mode == "morning":
            context["unconfirmed_yesterday"] = await _unconfirmed_yesterday(
                pool, owner_id, target_date, zone,
            )
            context["weather_note"] = await _weather_note(
                settings, context.get("routine") or {}, target_date, zone,
            )
        if mode == "evening":
            context["unfinished_today"] = await _unfinished_today(pool, owner_id, current, zone)
            tool_events.append({"tool": "unfinished_today", "rows": len(context["unfinished_today"])})
        candidates = _candidates(context, target_date, current, zone)
        pending = await pool.fetch(
            """SELECT command FROM proposals WHERE owner_id=$1 AND status='pending'
            AND expires_at>now() AND command->>'type' IN ('reschedule_entry','reschedule_task')""",
            owner_id,
        )
        pending_targets = set()
        for item in pending:
            command_data = json.loads(item["command"])
            payload = command_data.get("data", {})
            pending_targets.add((command_data.get("type"),
                                 payload.get("entry_id") or payload.get("task_id"),
                                 payload.get("expected_version")))
        candidates = [item for item in candidates if (
            item[1].type,
            item[1].data.get("entry_id") or item[1].data.get("task_id"),
            item[1].data.get("expected_version"),
        ) not in pending_targets]
        chosen, priority_fallback = await _choose_priorities(settings, context, candidates)
        if not chosen and candidates:
            chosen = [item[0] for item in candidates[:3]]
        if mode == "morning":
            chosen = chosen[:1]
        context["model_fallback"] = priority_fallback
        selected_by_id = {key: (command, reason) for key, command, reason in candidates}
        proposal_ids: list[str] = []
        proposal_notifications: list[tuple[uuid.UUID, str]] = []
        inserted_keys: list[str] = []
        async with pool.acquire() as conn:
            async with conn.transaction():
                if mode == "on_demand":
                    await conn.execute("DELETE FROM agent_dialogue_focus WHERE owner_id=$1", owner_id)
                for key in chosen:
                    command, reason = selected_by_id[key]
                    command.payload()
                    proposal_id = uuid.uuid4()
                    source = f"agent:{target_date}:{key}"
                    inserted = await conn.fetchval(
                        """INSERT INTO proposals(id,owner_id,source,command,reason,expires_at)
                        VALUES ($1,$2,$3,$4::jsonb,$5,$6) ON CONFLICT(owner_id,source) DO NOTHING
                        RETURNING id""", proposal_id, owner_id, source,
                        command.model_dump_json(), reason, end.astimezone(timezone.utc),
                    )
                    if inserted:
                        proposal_ids.append(str(inserted))
                        inserted_keys.append(key)
                        proposal_notifications.append((inserted, reason))
                summary = _summary(context, target_date, mode, zone, len(proposal_ids))
                if mode != "on_demand":
                    for index, offset in enumerate(range(0, len(summary), 4000)):
                        await conn.execute(
                            """INSERT INTO notification_outbox(id,owner_id,dedupe_key,channel,kind,payload)
                            VALUES ($1,$2,$3,'telegram','agent_brief',$4::jsonb) ON CONFLICT DO NOTHING""",
                            uuid.uuid4(), owner_id, f"agent_brief:{mode}:{target_date}:{index}",
                            json.dumps({"text": summary[offset:offset + 4000]}, ensure_ascii=False),
                        )
                for proposal_id, reason in proposal_notifications:
                    await conn.execute(
                        """INSERT INTO notification_outbox(id,owner_id,dedupe_key,channel,kind,payload)
                        VALUES ($1,$2,$3,'telegram','proposal',$4::jsonb) ON CONFLICT DO NOTHING""",
                        uuid.uuid4(), owner_id, f"proposal:{proposal_id}",
                        json.dumps({"proposal_id": str(proposal_id), "reason": reason}, ensure_ascii=False),
                    )
                context["proposal_ids"] = proposal_ids
                if mode == "on_demand" and len(proposal_ids) == 1:
                    focused_command = selected_by_id[inserted_keys[0]][0]
                    id_key = "entry_id" if focused_command.type == "reschedule_entry" else "task_id"
                    entity_id = uuid.UUID(str(focused_command.data[id_key]))
                    await conn.execute(
                        """INSERT INTO agent_dialogue_focus(owner_id,brief_id,proposal_id,entity_type,
                        entity_id,expires_at) VALUES ($1,$2,$3,$4,$5,now()+interval '30 minutes')
                        ON CONFLICT(owner_id) DO UPDATE SET brief_id=EXCLUDED.brief_id,
                        proposal_id=EXCLUDED.proposal_id,entity_type=EXCLUDED.entity_type,
                        entity_id=EXCLUDED.entity_id,expires_at=EXCLUDED.expires_at""",
                        owner_id, brief_id, uuid.UUID(proposal_ids[0]), focused_command.type, entity_id,
                    )
                await conn.execute(
                    """UPDATE agent_briefs SET status='ready',summary=$3,context=$4::jsonb,
                    tool_events=$5::jsonb,updated_at=now() WHERE id=$1 AND owner_id=$2""",
                    brief_id, owner_id, summary, json.dumps(context, ensure_ascii=False),
                    json.dumps(tool_events),
                )
        return {"id": brief_id, "owner_id": owner_id, "target_date": target_date,
                "mode": mode, "status": "ready", "summary": summary, "context": context,
                "tool_events": tool_events}
    except Exception as exc:
        logger.exception("Daily agent plan failed")
        await pool.execute(
            """UPDATE agent_briefs SET status='failed',error_code=$3,updated_at=now()
            WHERE id=$1 AND owner_id=$2""", brief_id, owner_id, type(exc).__name__,
        )
        raise


async def generate_due_briefs(pool: asyncpg.Pool, settings: Settings, owner_id: int,
                              now: datetime | None = None) -> int:
    current = now or datetime.now(ZoneInfo(settings.timezone))
    today = current.astimezone(ZoneInfo(settings.timezone)).date()
    routine = await _routine(pool, owner_id, today)
    created = 0
    for mode, target in (("morning", today), ("evening", today + timedelta(days=1))):
        scheduled = brief_due_at(mode, today, routine, settings.timezone)
        if not scheduled <= current < datetime.combine(today + timedelta(days=1), time.min,
                                                        ZoneInfo(settings.timezone)):
            continue
        if mode == "morning" and current.hour >= 17:
            continue
        key = f"scheduled:{mode}:{today}"
        if await pool.fetchval(
            "SELECT 1 FROM agent_briefs WHERE owner_id=$1 AND dedupe_key=$2 AND status='ready'",
            owner_id, key,
        ):
            continue
        await create_brief(pool, settings, owner_id, target, mode, key,
                           request_text=f"Pregătește rezumatul {mode} pentru {target}", now=current)
        created += 1
    return created


async def resolve_agent_followup(pool: asyncpg.Pool, settings: Settings, owner_id: int,
                                 text: str) -> ActionResult | None:
    """Revise one recent reminder proposal when the user refers to the last class."""
    plain = unicodedata.normalize("NFD", text.casefold())
    plain = "".join(char for char in plain if unicodedata.category(char) != "Mn")
    if not re.search(r"\b(dupa|apoi)\b.*\b(curs|seminar|facultate)\b", plain):
        return None
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                """SELECT f.proposal_id,p.command,p.version FROM agent_dialogue_focus f
                JOIN proposals p ON p.id=f.proposal_id AND p.owner_id=f.owner_id
                WHERE f.owner_id=$1 AND f.expires_at>now() AND p.status='pending'
                FOR UPDATE OF p""", owner_id,
            )
            if row is None:
                return None
            command = Command.model_validate(json.loads(row["command"]))
            if command.type != "reschedule_entry":
                return ActionResult(status="needs_input", command_type="daily_plan",
                                    message="La ce reminder te referi? Spune-mi titlul lui.")
            target = datetime.fromisoformat(str(command.data["starts_at"]))
            zone = ZoneInfo(settings.timezone)
            day = target.astimezone(zone).date()
            start = datetime.combine(day, time.min, zone)
            end = datetime.combine(day + timedelta(days=1), time.min, zone)
            last_class = await conn.fetchrow(
                """SELECT title,ends_at FROM calendar_entries WHERE owner_id=$1 AND kind='academic'
                AND status='active' AND starts_at>=$2 AND starts_at<$3 AND ends_at IS NOT NULL
                ORDER BY ends_at DESC LIMIT 1""", owner_id, start, end,
            )
            if not last_class:
                return ActionResult(status="needs_input", command_type="daily_plan",
                                    message="Nu văd un curs în acea zi. La ce oră vrei reminderul?")
            new_at = last_class["ends_at"] + timedelta(minutes=15)
            if new_at <= datetime.now(zone):
                return ActionResult(status="needs_input", command_type="daily_plan",
                                    message="Ultimul curs s-a terminat deja. La ce oră vrei reminderul?")
            other = await conn.fetchval(
                """SELECT title FROM calendar_entries WHERE owner_id=$1 AND status='active'
                AND kind='event' AND starts_at<=$2 AND COALESCE(ends_at,starts_at+interval '15 minutes')>$2
                LIMIT 1""", owner_id, new_at,
            )
            if other:
                return ActionResult(status="needs_input", command_type="daily_plan",
                                    message=f"La ora de după curs ai «{other}». Ce altă oră preferi?")
            command.data["starts_at"] = new_at.isoformat()
            command.payload()
            reason = f"Îl mut după ultimul curs («{last_class['title']}»), la {new_at.astimezone(zone):%H:%M}?"
            updated = await conn.fetchval(
                """UPDATE proposals SET command=$3::jsonb,reason=$4,version=version+1
                WHERE id=$1 AND owner_id=$2 AND status='pending' AND version=$5 RETURNING version""",
                row["proposal_id"], owner_id, command.model_dump_json(), reason, row["version"],
            )
            if not updated:
                return ActionResult(status="needs_input", command_type="daily_plan",
                                    message="Propunerea s-a schimbat între timp. Deschide Mini App → Azi.")
            await conn.execute(
                """UPDATE notification_outbox SET status='sent',last_error='superseded',lease_until=NULL
                WHERE owner_id=$1 AND kind='proposal' AND status='pending'
                AND dedupe_key LIKE $2""", owner_id, f"proposal:{row['proposal_id']}%",
            )
            await conn.execute(
                """INSERT INTO notification_outbox(id,owner_id,dedupe_key,channel,kind,payload)
                VALUES ($1,$2,$3,'telegram','proposal',$4::jsonb) ON CONFLICT DO NOTHING""",
                uuid.uuid4(), owner_id, f"proposal:{row['proposal_id']}:v{updated}",
                json.dumps({"proposal_id": str(row["proposal_id"]), "reason": reason}, ensure_ascii=False),
            )
            return ActionResult(status="needs_input", command_type="daily_plan", message=reason,
                                details={"proposal_id": str(row["proposal_id"])})
