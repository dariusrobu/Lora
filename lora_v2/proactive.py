"""Evidence-based proposals generated from live commitments and academic conflicts."""

import json
import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import asyncpg

from lora_v2.config import Settings
from lora_v2.models import Command


async def _propose(
    conn: asyncpg.Connection,
    owner_id: int,
    source: str,
    reason: str,
    command: Command,
) -> bool:
    proposal_id = uuid.uuid4()
    inserted = await conn.fetchval(
        """INSERT INTO proposals(id,owner_id,source,command,reason,expires_at)
        VALUES ($1,$2,$3,$4::jsonb,$5,now()+interval '3 days')
        ON CONFLICT (owner_id,source) DO NOTHING RETURNING id""",
        proposal_id, owner_id, source, json.dumps(command.model_dump(mode="json")), reason,
    )
    if not inserted:
        return False
    await conn.execute(
        """INSERT INTO notification_outbox(id,owner_id,dedupe_key,channel,kind,payload)
        VALUES ($1,$2,$3,'telegram','proposal',$4::jsonb)
        ON CONFLICT DO NOTHING""",
        uuid.uuid4(), owner_id, f"proposal:{proposal_id}",
        json.dumps({"proposal_id": str(proposal_id), "reason": reason}),
    )
    return True


async def generate_proposals(
    pool: asyncpg.Pool,
    settings: Settings,
    owner_id: int,
    now: datetime | None = None,
) -> int:
    """Generate at most two unsolicited proposals a day, plus explicit follow-ups."""
    current = now or datetime.now(ZoneInfo(settings.timezone))
    local_day = current.astimezone(ZoneInfo(settings.timezone)).date()
    created = 0
    async with pool.acquire() as conn:
        async with conn.transaction():
            followups = await conn.fetch(
                """SELECT id,title,starts_at,version FROM calendar_entries
                WHERE owner_id=$1 AND status='active' AND followup_at <= $2
                AND followup_at >= $2-interval '24 hours' ORDER BY followup_at LIMIT 20""",
                owner_id, current,
            )
            for row in followups:
                proposed_at = row["starts_at"] + timedelta(days=1)
                command = Command(type="reschedule_entry", data={
                    "entry_id": str(row["id"]), "starts_at": proposed_at.isoformat(),
                    "expected_version": row["version"],
                })
                source = f"followup:{row['id']}:v{row['version']}"
                reason = f"Ai reușit să faci «{row['title']}»? Alege «Am făcut» sau «Mută pe mâine»."
                if await _propose(conn, owner_id, source, reason, command):
                    created += 1

            already = await conn.fetchval(
                """SELECT count(*) FROM proposals WHERE owner_id=$1 AND source LIKE $2""",
                owner_id, f"conflict:{local_day.isoformat()}:%",
            )
            allowance = max(0, 2 - already)
            if allowance:
                conflicts = await conn.fetch(
                    """SELECT e.id,e.title,e.starts_at,e.version,a.ends_at AS class_ends
                    FROM calendar_entries e JOIN calendar_entries a
                    ON a.owner_id=e.owner_id AND a.kind='academic' AND a.status='active'
                    AND e.starts_at >= a.starts_at AND e.starts_at < a.ends_at
                    WHERE e.owner_id=$1 AND e.kind='reminder' AND e.status='active'
                    AND e.starts_at >= $2 AND e.starts_at < $3
                    ORDER BY e.starts_at LIMIT $4""",
                    owner_id, current, current + timedelta(days=2), allowance,
                )
                for row in conflicts:
                    suggested = row["class_ends"] + timedelta(minutes=15)
                    command = Command(type="reschedule_entry", data={
                        "entry_id": str(row["id"]), "starts_at": suggested.isoformat(),
                        "expected_version": row["version"],
                    })
                    source = f"conflict:{local_day.isoformat()}:{row['id']}"
                    reason = f"«{row['title']}» se suprapune cu facultatea. Îl mut după curs?"
                    if await _propose(conn, owner_id, source, reason, command):
                        created += 1
    return created


async def decide_proposal(
    pool: asyncpg.Pool,
    settings: Settings,
    owner_id: int,
    proposal_id: uuid.UUID,
    accept: bool,
):
    """A proposal never mutates domain data before the user's approval."""
    from lora_v2.service import execute_command

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT command,status,expires_at FROM proposals WHERE id=$1 AND owner_id=$2",
            proposal_id, owner_id,
        )
    if not row or row["status"] != "pending" or row["expires_at"] <= datetime.now(ZoneInfo("UTC")):
        return None
    if not accept:
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE proposals SET status='rejected' WHERE id=$1 AND owner_id=$2 AND status='pending'",
                proposal_id, owner_id,
            )
        return None
    command = Command.model_validate(json.loads(row["command"]))
    if command.type in {"delete_entity", "update_entity"}:
        from lora_v2.mutations import apply_mutation_proposal

        result = await apply_mutation_proposal(pool, settings, owner_id, command)
    else:
        result = await execute_command(
            pool, settings, owner_id, command, idempotency_key=f"proposal:{proposal_id}"
        )
    if result.status in ("saved", "already_done"):
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE proposals SET status='accepted' WHERE id=$1 AND owner_id=$2 AND status='pending'",
                proposal_id, owner_id,
            )
    return result


async def decide_followup(
    pool: asyncpg.Pool,
    settings: Settings,
    owner_id: int,
    proposal_id: uuid.UUID,
    choice: str,
):
    """Resolve a completion check as done or rescheduled, never by a vague yes/no."""
    from lora_v2.service import execute_command

    if choice not in {"done", "tomorrow"}:
        raise ValueError("Unknown follow-up choice")
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT source,command,status,expires_at FROM proposals WHERE id=$1 AND owner_id=$2",
            proposal_id, owner_id,
        )
    if (not row or not row["source"].startswith("followup:") or row["status"] != "pending"
            or row["expires_at"] <= datetime.now(ZoneInfo("UTC"))):
        return None
    planned = Command.model_validate(json.loads(row["command"]))
    payload = planned.payload()
    if planned.type != "reschedule_entry":
        raise ValueError("Invalid follow-up proposal")
    command = planned if choice == "tomorrow" else Command(type="complete_entry", data={
        "entry_id": str(payload.entry_id), "expected_version": payload.expected_version,
    })
    result = await execute_command(
        pool, settings, owner_id, command,
        idempotency_key=f"proposal:{proposal_id}:{choice}",
    )
    if result.status in {"saved", "already_done"}:
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE proposals SET status='accepted' WHERE id=$1 AND owner_id=$2 AND status='pending'",
                proposal_id, owner_id,
            )
    return result
