"""Capture workflow: retryable AI interpretation with per-action receipts."""

import json
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

import asyncpg
from pydantic import ValidationError

from lora_v2.agent import Interpretation, interpret_capture
from lora_v2.config import Settings
from lora_v2.models import ActionResult, Command
from lora_v2.media import interpret_photo, transcribe_voice
from lora_v2.meal_dialogue import remember_meal_question, resolve_meal_answer
from lora_v2.mutations import plan_mutation
from lora_v2.grounding import grounding_issue
from lora_v2.rules import extract_common
from lora_v2.service import execute_command


def _preview(command: Command) -> str:
    data = command.data
    if command.type == "create_calendar_entry":
        return f"{data.get('title')} · {data.get('starts_at')} · alerte {data.get('alert_offsets_minutes', [])} min"
    if command.type == "log_expense":
        return f"{data.get('amount')} {data.get('currency', 'RON')} · {data.get('category')} · {data.get('merchant') or data.get('description') or ''}"
    if command.type == "log_income":
        return f"Venit: {data.get('amount')} {data.get('currency', 'RON')} · {data.get('source') or data.get('description') or ''}"
    if command.type == "log_meal":
        return f"Masă: {data.get('description') or ', '.join(item.get('name', '') for item in data.get('items', []))} (estimare)"
    if command.type == "log_workout":
        return f"Antrenament: {data.get('activity')}, {data.get('duration_minutes')} min"
    if command.type == "log_health":
        return f"Sănătate {data.get('log_date')}: {data.get('water_ml_delta') or 0} ml apă, {data.get('weight_kg') or '—'} kg"
    return str(data.get("title") or data.get("name") or command.type)


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
            ) RETURNING raw_text,content_type,attachment_ref""",
            capture_id, owner_id,
        )
    if row is None:
        return []
    content = row["raw_text"]
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
        meal_answer = (await resolve_meal_answer(pool, owner_id, content)
                       if row["content_type"] in {"text", "voice"} else None)
        if row["content_type"] in {"text", "voice"} and meal_answer is None:
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
        elif row["content_type"] == "photo" and row["attachment_ref"]:
            interpretation = await interpret_photo(settings, row["attachment_ref"], row["raw_text"])
        else:
            rules, remaining = extract_common(content, datetime.now(ZoneInfo(settings.timezone)), settings.timezone)
            model = await interpret_capture(pool, settings, owner_id, remaining) if remaining else Interpretation()
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
        command = candidate.as_command()
        if (candidate.type == "log_meal" and candidate.missing_information ==
                "Sunt gramajele cântărite crude sau după gătire?"):
            await remember_meal_question(pool, owner_id, capture_id, candidate)
            needs_input = True
            results.append(ActionResult(status="needs_input", command_type="log_meal",
                message=candidate.missing_information))
            continue
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
            candidate, content, settings, datetime.now(ZoneInfo(settings.timezone))
        )
        if issue:
            needs_input = True
            results.append(ActionResult(
                status="needs_input", command_type=command.type, message=issue,
            ))
            continue
        if candidate.confidence < 0.85 or candidate.missing_information:
            needs_input = True
            reason = f"Verifică înainte de salvare: {_preview(command)}"
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

    async with pool.acquire() as conn:
        await conn.execute(
            """UPDATE captures SET status=$3,processed_at=now(),processing_started_at=NULL
            WHERE id=$1 AND owner_id=$2""",
            capture_id, owner_id, "needs_input" if needs_input else "processed",
        )
    return results
