"""Capture workflow: retryable AI interpretation with per-action receipts."""

import json
import uuid
import unicodedata
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import asyncpg
from pydantic import ValidationError

from lora_v2.agent import Interpretation, interpret_capture
from lora_v2.config import Settings
from lora_v2.models import ActionResult, Command
from lora_v2.media import interpret_photo, transcribe_voice
from lora_v2.meal_dialogue import remember_meal_question, resolve_meal_answer
from lora_v2.expense_dialogue import remember_expense_question, resolve_expense_answer
from lora_v2.mutations import plan_mutation
from lora_v2.nutrition import enrich_meal_candidate
from lora_v2.proposal_dialogue import resolve_proposal_reply
from lora_v2.grounding import grounding_issue
from lora_v2.rules import extract_common
from lora_v2.service import execute_command


def _preview(command: Command) -> str:
    data = command.data
    if command.type == "create_calendar_entry":
        starts_at = datetime.fromisoformat(str(data["starts_at"]))
        offsets = data.get("alert_offsets_minutes", [])
        alerts = []
        if 30 in offsets:
            alerts.append("cu 30 min înainte")
        if 0 in offsets:
            alerts.append("la ora stabilită")
        other_offsets = [value for value in offsets if value not in {0, 30}]
        alerts.extend(f"cu {value} min înainte" for value in other_offsets)
        alert_text = f" · alerte {', '.join(alerts)}" if alerts else ""
        return f"{data.get('title')} · {starts_at:%d.%m.%Y, %H:%M}{alert_text}"
    if command.type == "log_expense":
        return f"{data.get('amount')} {data.get('currency', 'RON')} · {data.get('category')} · {data.get('merchant') or data.get('description') or ''}"
    if command.type == "log_income":
        return f"Venit: {data.get('amount')} {data.get('currency', 'RON')} · {data.get('source') or data.get('description') or ''}"
    if command.type == "log_meal":
        lines = [f"Masă: {data.get('description') or 'estimare'}"]
        for item in data.get("items", [])[:8]:
            portion = f"{item['grams']} g" if item.get("grams") is not None else "gramaj necunoscut"
            nutrition = f"{item['calories']} kcal" if item.get("calories") is not None else "macro lipsă"
            source = f" · {item['nutrition_provider']}: {item['nutrition_source_title']}" if item.get("nutrition_provider") else ""
            lines.append(f"• {item.get('name', 'Aliment')}: {portion}, {nutrition}{source}")
        return "\n".join(lines)
    if command.type == "log_workout":
        return f"Antrenament: {data.get('activity')}, {data.get('duration_minutes')} min"
    if command.type == "log_health":
        return f"Sănătate {data.get('log_date')}: {data.get('water_ml_delta') or 0} ml apă, {data.get('weight_kg') or '—'} kg"
    return str(data.get("title") or data.get("name") or command.type)


def _category_key(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value.casefold().strip())
    return "".join(char for char in normalized if unicodedata.category(char) != "Mn")


async def _suggest_after_academic_classes(
    pool: asyncpg.Pool, owner_id: int, starts_at: datetime,
) -> tuple[datetime, str] | None:
    """Find the first 15-minute buffer after overlapping classes on that day."""
    local_day = starts_at.date()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT title,starts_at,ends_at FROM calendar_entries
            WHERE owner_id=$1 AND kind='academic' AND status='active'
            AND ends_at IS NOT NULL AND starts_at::date=$2 ORDER BY starts_at""",
            owner_id, local_day,
        )
    suggestion = starts_at
    first_conflict = None
    for row in rows:
        if row["starts_at"] <= suggestion < row["ends_at"]:
            if first_conflict is None:
                first_conflict = row["title"]
            suggestion = row["ends_at"] + timedelta(minutes=15)
    return (suggestion.astimezone(starts_at.tzinfo), first_conflict) if first_conflict else None


async def process_capture(
    pool: asyncpg.Pool,
    settings: Settings,
    owner_id: int,
    capture_id: uuid.UUID,
) -> list[ActionResult]:
    """Process each candidate once; ambiguous candidates become approval proposals."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """UPDATE captures SET status='processing',processing_started_at=now(),error_code=NULL
            WHERE id=$1 AND owner_id=$2 AND (
                status IN ('captured','failed') OR
                (status='processing' AND processing_started_at < now()-interval '2 minutes')
            ) RETURNING raw_text,content_type,attachment_ref,channel,created_at""",
            capture_id, owner_id,
        )
    if row is None:
        return []
    content = row["raw_text"]
    anchor = row["created_at"].astimezone(ZoneInfo(settings.timezone))
    model_deferred = False
    try:
        if row["content_type"] == "voice" and row["attachment_ref"]:
            content = await transcribe_voice(settings, row["attachment_ref"])
            if not content:
                raise ValueError("Empty transcription")
            async with pool.acquire() as conn:
                await conn.execute(
                    "UPDATE captures SET raw_text=$3 WHERE id=$1 AND owner_id=$2",
                    capture_id, owner_id, content,
                )
        proposal_answer = (await resolve_proposal_reply(pool, settings, owner_id, content, row["created_at"])
                           if row["content_type"] in {"text", "voice"} else None)
        if proposal_answer is not None:
            async with pool.acquire() as conn:
                await conn.execute(
                    """UPDATE captures SET status=$3,processed_at=now(),processing_started_at=NULL
                    WHERE id=$1 AND owner_id=$2""",
                    capture_id, owner_id,
                    "needs_input" if proposal_answer.status == "needs_input" else "processed",
                )
            return [proposal_answer]
        meal_answer = (await resolve_meal_answer(pool, owner_id, content)
                       if row["content_type"] in {"text", "voice"} else None)
        expense_answer = (await resolve_expense_answer(pool, owner_id, content)
                          if row["content_type"] in {"text", "voice"} and meal_answer is None else None)
        if row["content_type"] in {"text", "voice"} and meal_answer is None and expense_answer is None:
            planned = await plan_mutation(pool, settings, owner_id, capture_id, content)
            if planned is not None:
                async with pool.acquire() as conn:
                    await conn.execute(
                        """UPDATE captures SET status=$3,processed_at=now(),processing_started_at=NULL
                        WHERE id=$1 AND owner_id=$2""",
                        capture_id, owner_id,
                        "needs_input" if any(item.status == "needs_input" for item in planned) else "processed",
                    )
                return planned
        if meal_answer is not None:
            interpretation = Interpretation(actions=[meal_answer])
        elif expense_answer is not None:
            interpretation = Interpretation(actions=[expense_answer])
        elif row["content_type"] == "photo" and row["attachment_ref"]:
            interpretation = await interpret_photo(
                settings, row["attachment_ref"], row["raw_text"], now=anchor,
            )
        else:
            rules, remaining = extract_common(content, anchor, settings.timezone)
            model = Interpretation()
            if remaining:
                try:
                    model = await interpret_capture(pool, settings, owner_id, remaining, now=anchor)
                except Exception:
                    if not rules.actions or row["channel"] == "llm_retry":
                        raise
                    async with pool.acquire() as conn:
                        await conn.execute(
                            """INSERT INTO captures(id,owner_id,channel,external_id,content_type,
                            raw_text,status,processing_started_at,error_code,created_at)
                            VALUES ($1,$2,'llm_retry',$3,'text',$4,'failed',now(),'ModelUnavailable',$5)
                            ON CONFLICT (owner_id,channel,external_id) DO NOTHING""",
                            uuid.uuid4(), owner_id, str(capture_id), remaining, row["created_at"],
                        )
                    model_deferred = True
            interpretation = Interpretation(actions=rules.actions + model.actions,
                reply="\n".join(filter(None, [rules.reply, model.reply])) or None)
    except Exception as exc:
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE captures SET status='failed',error_code=$3 WHERE id=$1 AND owner_id=$2",
                capture_id, owner_id, type(exc).__name__,
            )
        raise

    results: list[ActionResult] = []
    needs_input = False
    for index, candidate in enumerate(interpretation.actions):
        if row["content_type"] == "photo" and candidate.type != "log_meal":
            needs_input = True
            results.append(ActionResult(status="needs_input", command_type=candidate.type,
                message="Din fotografia aceasta pot propune doar o masă. Spune-mi separat dacă vrei să salvez altceva."))
            continue
        if row["content_type"] == "photo" and candidate.type == "log_meal" and candidate.missing_information:
            needs_input = True
            results.append(ActionResult(status="needs_input", command_type="log_meal",
                message=f"{candidate.missing_information} Trimite fotografia din nou cu acest detaliu în descriere."))
            continue
        if (candidate.type == "log_meal" and candidate.missing_information ==
                "Sunt gramajele cântărite crude sau după gătire?"):
            await remember_meal_question(pool, owner_id, capture_id, candidate)
            needs_input = True
            results.append(ActionResult(status="needs_input", command_type="log_meal",
                message=candidate.missing_information))
            continue
        if candidate.type == "log_meal":
            candidate = await enrich_meal_candidate(candidate, settings)
        category_conflict = None
        learned_category = None
        if candidate.type == "log_expense":
            # Only an explicit owner choice may override a remembered rule.
            candidate.category_override = candidate is expense_answer
            candidate.expected_merchant_category = None
        if candidate.type == "log_expense" and candidate.merchant:
            async with pool.acquire() as conn:
                learned_category = await conn.fetchval(
                    "SELECT category FROM expense_category_rules WHERE owner_id=$1 AND merchant_key=$2",
                    owner_id, candidate.merchant.casefold().strip(),
                )
            if (learned_category and candidate.category and
                    _category_key(learned_category) != _category_key(candidate.category)):
                category_conflict = learned_category
                candidate.category_override = True
                candidate.expected_merchant_category = learned_category
        command = candidate.as_command()
        try:
            command.payload()
        except (ValidationError, ValueError) as exc:
            needs_input = True
            results.append(ActionResult(
                status="needs_input", command_type=command.type,
                message=candidate.missing_information or f"Lipsesc date pentru {command.type}.",
                details={"validation_error": type(exc).__name__},
            ))
            continue
        issue = grounding_issue(
            candidate, content, settings, anchor
        )
        if issue:
            needs_input = True
            results.append(ActionResult(
                status="needs_input", command_type=command.type, message=issue,
            ))
            continue
        if (candidate.type == "create_calendar_entry" and candidate.kind == "reminder"
                and candidate.starts_at and candidate.confidence < 0.85
                and "amia" in content.casefold()):
            start = datetime.fromisoformat(candidate.starts_at).astimezone(ZoneInfo(settings.timezone))
            suggested = await _suggest_after_academic_classes(pool, owner_id, start)
            if suggested:
                alternative, class_title = suggested
                candidate.starts_at = alternative.isoformat()
                candidate.missing_information = (
                    f"La ora propusă ai «{class_title}». Îți propun {alternative:%H:%M}, "
                    "după cursuri. Confirmi această oră?"
                )
                command = candidate.as_command()
                command.payload()
        if candidate.type == "log_expense" and not candidate.category and not learned_category:
            await remember_expense_question(pool, owner_id, capture_id, candidate)
            needs_input = True
            results.append(ActionResult(status="needs_input", command_type="log_expense",
                message=f"În ce categorie pun cheltuiala de {candidate.amount} {candidate.currency or 'RON'}? "
                        "Poți răspunde «mâncare», «transport» sau «categoria [nume]»."))
            continue
        if candidate.confidence < 0.85 or candidate.missing_information or candidate.type == "log_meal" or category_conflict:
            needs_input = True
            reason = (f"Pentru {candidate.merchant} ai folosit până acum categoria «{category_conflict}», "
                      f"dar această cheltuială pare «{candidate.category}». Confirmi categoria nouă?\n{_preview(command)}"
                      if category_conflict else f"Verifică înainte de salvare: {_preview(command)}")
            if row["content_type"] == "photo" and candidate.type == "log_meal":
                reason += "\nEstimare din fotografie: verifică porția și valorile înainte să confirmi."
            if candidate.missing_information:
                reason += f"\n{candidate.missing_information}"
            async with pool.acquire() as conn:
                proposal_id = uuid.uuid4()
                await conn.execute(
                    """INSERT INTO proposals(id,owner_id,source,command,reason,expires_at)
                    VALUES ($1,$2,$3,$4::jsonb,$5,now()+interval '7 days')
                    ON CONFLICT (owner_id,source) DO NOTHING""",
                    proposal_id, owner_id, f"capture:{capture_id}:{index}",
                    json.dumps(command.model_dump(mode="json")),
                    reason,
                )
                proposal_id = await conn.fetchval(
                    "SELECT id FROM proposals WHERE owner_id=$1 AND source=$2",
                    owner_id, f"capture:{capture_id}:{index}",
                )
                await conn.execute(
                    """INSERT INTO notification_outbox(id,owner_id,dedupe_key,channel,kind,payload)
                    VALUES ($1,$2,$3,'telegram','proposal',$4::jsonb) ON CONFLICT DO NOTHING""",
                    uuid.uuid4(), owner_id, f"proposal:{proposal_id}",
                    json.dumps({"proposal_id": str(proposal_id), "reason": reason}),
                )
            results.append(ActionResult(
                status="needs_input", command_type=command.type,
                message=reason,
                details={"proposal_id": str(proposal_id)},
            ))
            continue
        result = await execute_command(
            pool, settings, owner_id, command,
            idempotency_key=f"capture:{capture_id}:action:{index}",
            capture_id=capture_id,
        )
        results.append(result)
        needs_input = needs_input or result.status == "needs_input"

    if interpretation.reply:
        needs_input = True
        results.append(ActionResult(
            status="needs_input", command_type="clarification",
            message=interpretation.reply,
        ))
    if model_deferred:
        results.append(ActionResult(status="deferred", command_type="interpretation",
            message="Am procesat părțile clare. Restul mesajului rămâne salvat și îl reîncerc automat când modelul local revine."))

    async with pool.acquire() as conn:
        await conn.execute(
            """UPDATE captures SET status=$3,processed_at=now(),processing_started_at=NULL
            WHERE id=$1 AND owner_id=$2""",
            capture_id, owner_id, "needs_input" if needs_input else "processed",
        )
    return results
