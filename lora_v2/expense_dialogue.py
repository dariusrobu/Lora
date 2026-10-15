"""Keep an uncategorized expense for one short owner clarification."""

import json
import re
import unicodedata
import uuid

import asyncpg

from lora_v2.agent import Candidate


def _plain(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value.casefold().strip())
    return "".join(char for char in normalized if unicodedata.category(char) != "Mn")


_CATEGORIES = {
    "mancare": "mâncare", "transport": "transport", "locuinta": "locuință",
    "sanatate": "sănătate", "educatie": "educație", "sport": "sport",
    "abonamente": "abonamente", "cumparaturi": "cumpărături",
    "divertisment": "divertisment", "cadouri": "cadouri", "altele": "altele",
}


async def remember_expense_question(
    pool: asyncpg.Pool, owner_id: int, capture_id: uuid.UUID, candidate: Candidate,
) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO expense_clarifications(owner_id,candidate,source_capture_id,expires_at)
            VALUES ($1,$2::jsonb,$3,now()+interval '10 minutes')
            ON CONFLICT (owner_id) DO UPDATE SET candidate=EXCLUDED.candidate,
                source_capture_id=EXCLUDED.source_capture_id,expires_at=EXCLUDED.expires_at,
                created_at=now()""",
            owner_id, json.dumps(candidate.model_dump(mode="json")), capture_id,
        )


async def resolve_expense_answer(
    pool: asyncpg.Pool, owner_id: int, answer: str,
) -> Candidate | None:
    """Ignore unrelated messages; never turn a vague reply into a category."""
    simple = _plain(answer.strip(" .!?"))
    category = _CATEGORIES.get(simple)
    if category is None:
        explicit = re.fullmatch(r"(?:in )?categoria ([\wăâîșț -]{2,60})", simple)
        if explicit and len(explicit.group(1).split()) <= 3:
            category = re.sub(r"^(?:în |in )?categoria\s+", "", answer.strip(" .!?"), flags=re.IGNORECASE)
    if category is None:
        return None
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """DELETE FROM expense_clarifications WHERE owner_id=$1 AND expires_at>now()
            RETURNING candidate""", owner_id,
        )
    if row is None:
        return None
    candidate = Candidate.model_validate(json.loads(row["candidate"]))
    if candidate.type != "log_expense":
        raise ValueError("Invalid pending expense")
    candidate.category = category
    candidate.confidence = 0.8
    candidate.missing_information = None
    candidate.evidence = None
    return candidate
