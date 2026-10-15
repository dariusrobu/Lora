"""Resolve the raw-versus-cooked question before a meal can be proposed."""

import json
import re
import unicodedata
import uuid

import asyncpg

from lora_v2.agent import Candidate


def _plain(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value.casefold())
    return "".join(char for char in normalized if unicodedata.category(char) != "Mn")


async def remember_meal_question(
    pool: asyncpg.Pool, owner_id: int, capture_id: uuid.UUID, candidate: Candidate,
) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO meal_clarifications(owner_id,candidate,source_capture_id,expires_at)
            VALUES ($1,$2::jsonb,$3,now()+interval '10 minutes')
            ON CONFLICT (owner_id) DO UPDATE SET candidate=EXCLUDED.candidate,
                source_capture_id=EXCLUDED.source_capture_id,expires_at=EXCLUDED.expires_at,
                created_at=now()""",
            owner_id, json.dumps(candidate.model_dump(mode="json")), capture_id,
        )


async def resolve_meal_answer(
    pool: asyncpg.Pool, owner_id: int, answer: str,
) -> Candidate | None:
    """Only a narrow preparation answer consumes the pending meal."""
    simple = re.sub(r"\s+", " ", _plain(answer.strip(" .!?")))
    if re.fullmatch(r"(?:sunt |erau |le.am cantarit )?(?:crude|crud|inainte de gatire)", simple):
        preparation = "crud"
    elif re.fullmatch(r"(?:sunt |erau |le.am cantarit )?(?:gatite|gatit|dupa gatire)", simple):
        preparation = "gătit"
    else:
        return None
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """DELETE FROM meal_clarifications WHERE owner_id=$1 AND expires_at>now()
            RETURNING candidate""", owner_id,
        )
    if row is None:
        return None
    candidate = Candidate.model_validate(json.loads(row["candidate"]))
    if candidate.type != "log_meal" or not candidate.items:
        raise ValueError("Invalid pending meal")
    candidate.items = [item.model_copy(update={"name": f"{item.name} ({preparation})"})
                       for item in candidate.items]
    candidate.description = f"{candidate.description or 'Masă'} · gramaje cântărite {preparation}"
    candidate.confidence = 0.8
    candidate.missing_information = None
    candidate.evidence = None
    return candidate
