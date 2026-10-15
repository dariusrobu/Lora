"""Durable Telegram delivery; a successful API response is recorded explicitly."""

import json
import uuid
from datetime import datetime, timedelta, timezone

import asyncpg
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup


async def send_pending_telegram(
    pool: asyncpg.Pool,
    bot: Bot,
    owner_id: int,
    now: datetime | None = None,
    interactive: bool = True,
) -> int:
    current = now or datetime.now(timezone.utc)
    delivered = 0
    async with pool.acquire() as conn:
        outbox = await conn.fetch(
            """UPDATE notification_outbox SET status='leased',lease_until=$2+interval '90 seconds',attempts=attempts+1
            WHERE id IN (
                SELECT id FROM notification_outbox WHERE owner_id=$1 AND channel='telegram'
                AND due_at <= $2 AND (status='pending' OR (status='leased' AND lease_until < $2))
                ORDER BY due_at LIMIT 20 FOR UPDATE SKIP LOCKED
            ) RETURNING id,kind,payload,attempts""",
            owner_id, current,
        )
    for row in outbox:
        payload = json.loads(row["payload"])
        try:
            if row["kind"] == "alert":
                async with pool.acquire() as conn:
                    current_version = await conn.fetchrow(
                        "SELECT version,status FROM calendar_entries WHERE id=$1 AND owner_id=$2",
                        uuid.UUID(payload["entry_id"]), owner_id,
                    )
                if (not current_version or current_version["status"] != "active"
                        or current_version["version"] != payload["entry_version"]):
                    async with pool.acquire() as conn:
                        async with conn.transaction():
                            await conn.execute(
                                "UPDATE notification_outbox SET status='sent',last_error='superseded' WHERE id=$1",
                                row["id"],
                            )
                            if payload.get("alert_id"):
                                await conn.execute(
                                    "UPDATE alert_occurrences SET status='cancelled' WHERE id=$1",
                                    uuid.UUID(payload["alert_id"]),
                                )
                    continue
            if row["kind"] == "task_alert":
                async with pool.acquire() as conn:
                    task_version = await conn.fetchrow(
                        "SELECT version,status FROM tasks WHERE id=$1 AND owner_id=$2",
                        uuid.UUID(payload["task_id"]), owner_id,
                    )
                if (not task_version or task_version["status"] != "pending"
                        or task_version["version"] != payload["task_version"]):
                    async with pool.acquire() as conn:
                        await conn.execute(
                            "UPDATE notification_outbox SET status='sent',last_error='superseded' WHERE id=$1",
                            row["id"],
                        )
                    continue
            if row["kind"] == "proposal":
                proposal_id = payload["proposal_id"]
                if interactive:
                    async with pool.acquire() as conn:
                        source = await conn.fetchval(
                            "SELECT source FROM proposals WHERE id=$1 AND owner_id=$2",
                            uuid.UUID(proposal_id), owner_id,
                        )
                    if source and source.startswith("followup:"):
                        keyboard = InlineKeyboardMarkup([[
                            InlineKeyboardButton("Am făcut", callback_data=f"v2:f:{proposal_id}:done"),
                            InlineKeyboardButton("Mută pe mâine", callback_data=f"v2:f:{proposal_id}:tomorrow"),
                        ]])
                    else:
                        keyboard = InlineKeyboardMarkup([[
                            InlineKeyboardButton("Da, fă asta", callback_data=f"v2:p:{proposal_id}:yes"),
                            InlineKeyboardButton("Nu acum", callback_data=f"v2:p:{proposal_id}:no"),
                        ]])
                    await bot.send_message(chat_id=owner_id, text=payload["reason"], reply_markup=keyboard)
                else:
                    await bot.send_message(chat_id=owner_id, text=payload["reason"] + "\nAlege în Mini App → Azi.")
            elif row["kind"] == "alert" and payload.get("entry_kind") == "reminder":
                entry_id = payload["entry_id"]
                version = payload["entry_version"]
                keyboard = InlineKeyboardMarkup([[
                    InlineKeyboardButton("Gata", callback_data=f"v2:e:{entry_id}:{version}:done"),
                    InlineKeyboardButton("Mâine", callback_data=f"v2:e:{entry_id}:{version}:tomorrow"),
                ]])
                if interactive:
                    await bot.send_message(chat_id=owner_id, text=payload["text"], reply_markup=keyboard)
                else:
                    await bot.send_message(chat_id=owner_id, text=payload["text"])
            elif row["kind"] == "task_alert":
                keyboard = InlineKeyboardMarkup([[
                    InlineKeyboardButton("Gata", callback_data=f"v2:t:{payload['task_id']}:{payload['task_version']}:done"),
                ]])
                if interactive:
                    await bot.send_message(chat_id=owner_id, text=payload["text"], reply_markup=keyboard)
                else:
                    await bot.send_message(chat_id=owner_id, text=payload["text"])
            else:
                await bot.send_message(chat_id=owner_id, text=payload["text"])
        except Exception as exc:
            delay = min(300, 2 ** min(row["attempts"], 8))
            async with pool.acquire() as conn:
                await conn.execute(
                    """UPDATE notification_outbox SET status='pending',lease_until=NULL,
                    due_at=$2,last_error=$3 WHERE id=$1""",
                    row["id"], current + timedelta(seconds=delay), type(exc).__name__,
                )
        else:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    await conn.execute(
                        "UPDATE notification_outbox SET status='sent',sent_at=$2,lease_until=NULL WHERE id=$1",
                        row["id"], current,
                    )
                    if row["kind"] == "alert" and payload.get("alert_id"):
                        await conn.execute(
                            "UPDATE alert_occurrences SET status='sent',sent_at=$2 WHERE id=$1",
                            uuid.UUID(payload["alert_id"]), current,
                        )
            delivered += 1
    return delivered


async def queue_due_alerts(pool: asyncpg.Pool, owner_id: int, now: datetime | None = None) -> int:
    """Project due alerts into outbox with a stable dedupe key."""
    current = now or datetime.now(timezone.utc)
    queued = 0
    async with pool.acquire() as conn:
        async with conn.transaction():
            rows = await conn.fetch(
                """SELECT a.id,a.purpose,e.id AS entry_id,e.title,e.status,e.version,e.kind FROM alert_occurrences a
                JOIN calendar_entries e ON e.id=a.entry_id
                WHERE a.owner_id=$1 AND a.status='pending' AND a.alert_at <= $2
                AND a.alert_at >= $2-interval '1 day'
                ORDER BY a.alert_at LIMIT 50 FOR UPDATE OF a SKIP LOCKED""",
                owner_id, current,
            )
            for row in rows:
                if row["status"] != "active":
                    await conn.execute("UPDATE alert_occurrences SET status='cancelled' WHERE id=$1", row["id"])
                    continue
                text = f"⏰ {row['title']}"
                if row["purpose"] != "before_0m":
                    minutes = row["purpose"].removeprefix("before_").removesuffix("m")
                    text = f"⏰ Peste {minutes} min: {row['title']}"
                await conn.execute(
                    """INSERT INTO notification_outbox(id,owner_id,dedupe_key,channel,kind,payload)
                    VALUES ($1,$2,$3,'telegram','alert',$4::jsonb) ON CONFLICT DO NOTHING""",
                    uuid.uuid4(), owner_id, f"alert:{row['id']}",
                    json.dumps({"text": text, "alert_id": str(row["id"]), "entry_id": str(row["entry_id"]),
                                "entry_version": row["version"], "entry_kind": row["kind"]}),
                )
                await conn.execute("UPDATE alert_occurrences SET status='queued' WHERE id=$1", row["id"])
                queued += 1
            tasks = await conn.fetch(
                """SELECT id,title,version FROM tasks WHERE owner_id=$1 AND status='pending'
                AND due_at <= $2 AND due_at >= $2-interval '1 day'
                ORDER BY due_at LIMIT 50""",
                owner_id, current,
            )
            for task in tasks:
                inserted = await conn.fetchval(
                    """INSERT INTO notification_outbox(id,owner_id,dedupe_key,channel,kind,payload)
                    VALUES ($1,$2,$3,'telegram','task_alert',$4::jsonb)
                    ON CONFLICT DO NOTHING RETURNING id""",
                    uuid.uuid4(), owner_id, f"task_due:{task['id']}:v{task['version']}",
                    json.dumps({"text": f"⏰ Task: {task['title']}",
                                "task_id": str(task["id"]), "task_version": task["version"]}),
                )
                queued += bool(inserted)
    return queued


async def queue_apple_conflicts(pool: asyncpg.Pool, owner_id: int) -> int:
    """Notify once per unresolved two-way sync conflict."""
    queued = 0
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT id FROM apple_sync_conflicts WHERE owner_id=$1 AND status='pending'
            ORDER BY created_at LIMIT 20""",
            owner_id,
        )
        for row in rows:
            inserted = await conn.fetchval(
                """INSERT INTO notification_outbox(id,owner_id,dedupe_key,channel,kind,payload)
                VALUES ($1,$2,$3,'telegram','apple_conflict',$4::jsonb)
                ON CONFLICT DO NOTHING RETURNING id""",
                uuid.uuid4(), owner_id, f"apple_conflict:{row['id']}",
                json.dumps({"text": "Apple Reminders și Lora au modificări diferite. Deschide Mini App → Azi pentru a compara și alege."}),
            )
            queued += bool(inserted)
    return queued
