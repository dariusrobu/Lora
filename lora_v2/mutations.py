"""Grounded conversational corrections that need an explicit target and approval."""

import json
import re
import unicodedata
import uuid
from typing import Any

import asyncpg

from lora_v2.config import Settings
from lora_v2.crud import EditRequest, delete_entity, update_entity
from lora_v2.models import ActionResult, Command


def _plain(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value.casefold())
    return "".join(char for char in normalized if unicodedata.category(char) != "Mn")


_NOUNS = {
    "cheltu(?:ial|iel)": "expense", "task": "task", "reminder": "calendar_entry",
    "eveniment": "calendar_entry", "proiect": "project", "venit": "income",
    "mas(?:a|e)": "meal", "antrenament": "workout", "sanatat": "health",
}

_LATEST_SQL = {
    "expense": "SELECT id,version,amount,currency,category,merchant,description,spent_at FROM expenses WHERE owner_id=$1 AND deleted_at IS NULL ORDER BY created_at DESC LIMIT 1",
    "income": "SELECT id,version,amount,currency,category,source,description,received_at FROM incomes WHERE owner_id=$1 AND deleted_at IS NULL ORDER BY created_at DESC LIMIT 1",
    "task": "SELECT id,version,title FROM tasks WHERE owner_id=$1 AND status='pending' ORDER BY created_at DESC LIMIT 1",
    "project": "SELECT id,version,name AS title FROM projects WHERE owner_id=$1 AND status!='archived' ORDER BY created_at DESC LIMIT 1",
    "meal": "SELECT id,version,description AS title FROM meals WHERE owner_id=$1 AND deleted_at IS NULL ORDER BY created_at DESC LIMIT 1",
    "workout": "SELECT id,version,activity AS title FROM workouts WHERE owner_id=$1 AND deleted_at IS NULL ORDER BY created_at DESC LIMIT 1",
    "health": "SELECT id,version,log_date::text AS title FROM health_entries WHERE owner_id=$1 AND deleted_at IS NULL ORDER BY created_at DESC LIMIT 1",
    "event": "SELECT id,version,title FROM calendar_entries WHERE owner_id=$1 AND kind='event' AND status='active' ORDER BY created_at DESC LIMIT 1",
    "reminder": "SELECT id,version,title FROM calendar_entries WHERE owner_id=$1 AND kind='reminder' AND status='active' ORDER BY created_at DESC LIMIT 1",
}


def _kind_for_text(text: str) -> tuple[str, str] | None:
    simple = _plain(text)
    for noun, kind in _NOUNS.items():
        if re.search(rf"\b{noun}\w*\b", simple):
            if kind == "calendar_entry":
                return kind, "reminder" if noun == "reminder" else "event"
            return kind, kind
    return None


def _preview(kind: str, row: asyncpg.Record) -> str:
    if kind in {"expense", "income"}:
        title = row.get("merchant") if kind == "expense" else row.get("source")
        return f"{row['amount']} {row['currency']} · {title or row.get('description') or row.get('category') or kind}"
    return str(row.get("title") or kind)


async def _remember_question(
    pool: asyncpg.Pool, owner_id: int, text: str, expected: str,
) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO mutation_clarifications(owner_id,original_text,expected,expires_at)
            VALUES ($1,$2,$3,now()+interval '10 minutes')
            ON CONFLICT (owner_id) DO UPDATE SET original_text=EXCLUDED.original_text,
                expected=EXCLUDED.expected,expires_at=EXCLUDED.expires_at,
                created_at=now()""",
            owner_id, text, expected,
        )


async def _complete_question(pool: asyncpg.Pool, owner_id: int, text: str) -> str:
    simple = _plain(text.strip())
    async with pool.acquire() as conn:
        if re.match(r"^(?:sterge|elimina|scoate|schimba|modifica|corecteaza)\b", simple):
            await conn.execute("DELETE FROM mutation_clarifications WHERE owner_id=$1", owner_id)
            return text
        pending = await conn.fetchrow(
            """SELECT original_text,expected FROM mutation_clarifications
            WHERE owner_id=$1 AND expires_at>now()""", owner_id,
        )
        if pending is None:
            return text
        original = pending["original_text"]
        expected = pending["expected"]
        if expected in {"target", "last"}:
            if not re.search(r"\bultim\w*\b", simple):
                return text
            if expected == "target" and _kind_for_text(text) is None:
                return text
            combined = f"{original} {text}"
        elif expected == "category":
            # A short noun phrase is a category; full new requests pass through untouched.
            if (not re.fullmatch(r"(?:in\s+)?[\wăâîșț -]{2,80}", simple)
                    or len(simple.split()) > 3 or re.search(r"\d", simple)
                    or (not simple.startswith("in ") and len(simple.split()) != 1)):
                return text
            combined = f"{original} {text}" if simple.startswith("in ") else f"{original} în {text}"
        else:
            return text
        await conn.execute("DELETE FROM mutation_clarifications WHERE owner_id=$1", owner_id)
        return combined


async def plan_mutation(
    pool: asyncpg.Pool,
    settings: Settings,
    owner_id: int,
    capture_id: uuid.UUID,
    text: str,
) -> list[ActionResult] | None:
    """Plan only an unambiguous last-item edit/delete; other messages stay untouched."""
    text = await _complete_question(pool, owner_id, text)
    simple = _plain(text.strip())
    delete = bool(re.match(r"^(?:sterge|elimina|scoate)\b", simple))
    category_edit = bool(re.match(r"^(?:schimba|modifica|corecteaza)\s+categoria\b", simple))
    if not delete and not category_edit:
        return None
    target = _kind_for_text(text)
    if category_edit:
        target = ("expense", "expense") if re.search(r"\bcheltu(?:ial|iel)\w*\b", simple) else None
    if not target:
        await _remember_question(pool, owner_id, text, "target")
        return [ActionResult(status="needs_input", command_type="mutation",
            message="Ce element vrei să modific sau să șterg? Spune tipul și «ultimul/ultima»." )]
    kind, selector = target
    if not re.search(r"\bultim\w*\b", simple):
        await _remember_question(pool, owner_id, text, "last")
        return [ActionResult(status="needs_input", command_type="mutation",
            message="Care element anume? Poți spune «ultimul/ultima» sau îl poți alege din Mini App.")]
    async with pool.acquire() as conn:
        row = await conn.fetchrow(_LATEST_SQL[selector], owner_id)
    if row is None:
        return [ActionResult(status="needs_input", command_type="mutation",
            message="Nu găsesc un element activ de acest tip.")]
    if category_edit:
        match = re.search(r"\b(?:în|in|cu)\s+([^.,;!?]+)\s*$", text, re.IGNORECASE)
        if not match:
            await _remember_question(pool, owner_id, text, "category")
            return [ActionResult(status="needs_input", command_type="update_expense",
                message="În ce categorie vrei să pun ultima cheltuială?")]
        category = match.group(1).strip()
        if not category or len(category) > 80:
            return [ActionResult(status="needs_input", command_type="update_expense",
                message="Spune o categorie scurtă pentru cheltuială.")]
        data: dict[str, Any] = {
            "amount": str(row["amount"]), "currency": row["currency"],
            "category": category, "category_override": True,
            "merchant": row["merchant"], "description": row["description"],
            "spent_at": row["spent_at"].isoformat(),
        }
        command = Command(type="update_entity", data={"kind": "expense", "entity_id": str(row["id"]),
            "expected_version": row["version"], "data": data})
        reason = f"Schimb categoria pentru {_preview(kind, row)} din «{row['category']}» în «{category}»?"
    else:
        command = Command(type="delete_entity", data={"kind": kind, "entity_id": str(row["id"]),
            "expected_version": row["version"]})
        reason = f"Șterg {_preview(kind, row)}?"
    source = f"mutation:{capture_id}"
    async with pool.acquire() as conn:
        async with conn.transaction():
            proposal_id = uuid.uuid4()
            await conn.execute(
                """INSERT INTO proposals(id,owner_id,source,command,reason,expires_at)
                VALUES ($1,$2,$3,$4::jsonb,$5,now()+interval '1 day')
                ON CONFLICT (owner_id,source) DO NOTHING""",
                proposal_id, owner_id, source, json.dumps(command.model_dump(mode="json")), reason,
            )
            proposal_id = await conn.fetchval(
                "SELECT id FROM proposals WHERE owner_id=$1 AND source=$2", owner_id, source,
            )
            await conn.execute(
                """INSERT INTO notification_outbox(id,owner_id,dedupe_key,channel,kind,payload)
                VALUES ($1,$2,$3,'telegram','proposal',$4::jsonb) ON CONFLICT DO NOTHING""",
                uuid.uuid4(), owner_id, f"proposal:{proposal_id}",
                json.dumps({"proposal_id": str(proposal_id), "reason": reason}),
            )
    return [ActionResult(status="needs_input", command_type=command.type,
        message=f"Am găsit: {_preview(kind, row)}. Confirmă propunerea pentru modificare.",
        details={"proposal_id": str(proposal_id)})]


async def apply_mutation_proposal(
    pool: asyncpg.Pool, settings: Settings, owner_id: int, command: Command,
) -> ActionResult:
    data = command.data
    if command.type not in {"delete_entity", "update_entity"}:
        raise ValueError("Unknown mutation")
    kind = data.get("kind")
    if kind not in {"expense", "income", "task", "project", "meal", "workout", "health", "calendar_entry"}:
        raise ValueError("Unknown mutation entity")
    try:
        entity_id = uuid.UUID(str(data["entity_id"]))
        version = int(data["expected_version"])
    except (KeyError, ValueError, TypeError) as exc:
        raise ValueError("Invalid mutation target") from exc
    if command.type == "delete_entity":
        return await delete_entity(pool, owner_id, kind, entity_id, version)
    request = EditRequest.model_validate({"expected_version": version, "data": data.get("data")})
    return await update_entity(pool, settings, owner_id, kind, entity_id, request)
