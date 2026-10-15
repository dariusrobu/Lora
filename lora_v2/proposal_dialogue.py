"""Resolve short approval replies only when one recent capture proposal is unambiguous."""

import re
import unicodedata
import uuid
from datetime import datetime, timedelta

import asyncpg

from lora_v2.config import Settings
from lora_v2.models import ActionResult
from lora_v2.proactive import decide_proposal


def _plain(text: str) -> str:
    normalized = unicodedata.normalize("NFD", text.casefold().strip(" .!?"))
    return "".join(char for char in normalized if unicodedata.category(char) != "Mn")


async def resolve_proposal_reply(
    pool: asyncpg.Pool,
    settings: Settings,
    owner_id: int,
    text: str,
    captured_at: datetime,
) -> ActionResult | None:
    simple = re.sub(r"\s+", " ", _plain(text))
    if simple in {"da", "confirm", "confirma", "salveaza", "da, salveaza"}:
        accept = True
    elif simple in {"nu", "anuleaza", "nu, multumesc", "nu acum"}:
        accept = False
    else:
        return None

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT id,source FROM proposals WHERE owner_id=$1 AND status='pending'
            AND created_at >= $2 AND created_at <= $3
            AND expires_at > now() ORDER BY created_at DESC LIMIT 2""",
            owner_id, captured_at - timedelta(minutes=10), captured_at,
        )
    if not rows:
        return None
    if len(rows) > 1 or not rows[0]["source"].startswith("capture:"):
        return ActionResult(
            status="needs_input", command_type="proposal_decision",
            message="Nu pot lega acest răspuns de o singură propunere din conversație. Alege în Mini App → Azi.",
        )
    async with pool.acquire() as conn:
        another_question = await conn.fetchval(
            """SELECT EXISTS(SELECT 1 FROM meal_clarifications WHERE owner_id=$1 AND expires_at>now())
            OR EXISTS(SELECT 1 FROM expense_clarifications WHERE owner_id=$1 AND expires_at>now())
            OR EXISTS(SELECT 1 FROM mutation_clarifications WHERE owner_id=$1 AND expires_at>now())""",
            owner_id,
        )
    if another_question:
        return ActionResult(
            status="needs_input", command_type="proposal_decision",
            message="Ai și o clarificare deschisă. Alege propunerea în Mini App → Azi sau răspunde cu detaliul cerut.",
        )
    proposal_id: uuid.UUID = rows[0]["id"]
    result = await decide_proposal(pool, settings, owner_id, proposal_id, accept=accept)
    if accept:
        return result or ActionResult(
            status="needs_input", command_type="proposal_decision",
            message="Propunerea nu mai este disponibilă. Deschide Mini App → Azi.",
        )
    async with pool.acquire() as conn:
        status = await conn.fetchval(
            "SELECT status FROM proposals WHERE id=$1 AND owner_id=$2", proposal_id, owner_id,
        )
    if status != "rejected":
        return ActionResult(
            status="needs_input", command_type="proposal_decision",
            message="Propunerea a fost modificată între timp. Verifică în Mini App → Azi.",
        )
    return ActionResult(
        status="already_done", command_type="proposal_decision",
        message="Nu am salvat propunerea.",
    )
