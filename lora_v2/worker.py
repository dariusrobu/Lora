"""Background capture processing, proactive checks, and notification delivery."""

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

import asyncpg
from telegram import Bot

from lora_v2.config import Settings
from lora_v2.academic_calendar import materialize_schedule
from lora_v2.apple import pull_changes, push_pending
from lora_v2.apple_events import sync_events
from lora_v2.notifications import queue_apple_conflicts, queue_due_alerts, send_pending_telegram
from lora_v2.proactive import generate_proposals
from lora_v2.processor import process_capture

logger = logging.getLogger(__name__)


async def schedule_class_alerts(pool: asyncpg.Pool, owner_id: int) -> None:
    """Future class notifications only; no replay of the old scheduler's alerts."""
    await pool.execute(
        """UPDATE alert_occurrences a SET status='cancelled' FROM calendar_entries e
        WHERE a.entry_id=e.id AND a.owner_id=$1 AND e.kind='academic' AND a.status='pending'
        AND (e.status!='active' OR a.alert_at!=e.starts_at-interval '15 minutes')""", owner_id,
    )
    rows = await pool.fetch(
        """SELECT id,starts_at-interval '15 minutes' AS alert_at FROM calendar_entries
        WHERE owner_id=$1 AND kind='academic' AND status='active'
        AND starts_at-interval '15 minutes'>now()""", owner_id,
    )
    for row in rows:
        await pool.execute(
            """INSERT INTO alert_occurrences(id,owner_id,entry_id,alert_at,purpose)
            VALUES ($1,$2,$3,$4,'before_15m') ON CONFLICT DO NOTHING""",
            uuid.uuid4(), owner_id, row['id'], row['alert_at'],
        )


async def _queue_receipt(pool: asyncpg.Pool, owner_id: int, capture_id: uuid.UUID, text: str, stage: str) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO notification_outbox(id,owner_id,dedupe_key,channel,kind,payload)
            VALUES ($1,$2,$3,'telegram','receipt',$4::jsonb) ON CONFLICT DO NOTHING""",
            uuid.uuid4(), owner_id, f"capture_receipt:{capture_id}:{stage}", json.dumps({"text": text}),
        )


async def run_once(pool: asyncpg.Pool, bot: Bot, settings: Settings, refresh_academic: bool = True, sync_apple: bool = False,
                   interactive_notifications: bool = True, deliver_notifications: bool = True) -> None:
    owner_id = settings.telegram_user_id
    if refresh_academic:
        await materialize_schedule(pool, settings, owner_id, days=14)
    if sync_apple and settings.apple_sync_enabled:
        try:
            await pull_changes(pool, settings, owner_id)
            await push_pending(pool, settings, owner_id)
            await queue_apple_conflicts(pool, owner_id)
        except Exception as exc:
            # Apple availability must never interrupt Telegram reminders.
            logger.error("Apple sync failed: %s", type(exc).__name__)
    if sync_apple and settings.apple_events_enabled:
        try:
            result = await sync_events(pool, settings, owner_id)
            await pool.execute(
                """INSERT INTO integration_status(name,status,detail)
                VALUES ('apple_calendar',$1,$2::jsonb)
                ON CONFLICT(name) DO UPDATE SET status=EXCLUDED.status,
                detail=EXCLUDED.detail,checked_at=now()""",
                'error' if result['errors'] else 'conflict' if result['conflicts'] else 'ok',
                json.dumps(result),
            )
        except Exception as exc:
            logger.error("Apple Calendar sync failed: %s", type(exc).__name__)
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT id,channel FROM captures WHERE owner_id=$1 AND (
                status='captured' OR
                (status='failed' AND processing_started_at < now()-interval '5 minutes') OR
                (status='processing' AND processing_started_at < now()-interval '2 minutes')
            )
            ORDER BY created_at LIMIT 5""",
            owner_id,
        )
    for row in rows:
        try:
            results = await process_capture(pool, settings, owner_id, row["id"])
            if results:
                message = "\n".join(result.message for result in results)
            else:
                message = "Am păstrat mesajul, dar nu am găsit o acțiune de salvat."
            await _queue_receipt(pool, owner_id, row["id"], message, "result")
        except Exception:
            logger.exception("Capture processing failed: %s", row["id"])
            if row["channel"] != "llm_retry":
                await _queue_receipt(
                    pool, owner_id, row["id"],
                    "Am păstrat mesajul, dar nu l-am putut procesa încă. Voi reîncerca.", "retry",
                )
    if deliver_notifications:
        await deliver_once(pool, bot, settings, interactive_notifications)


async def deliver_once(pool: asyncpg.Pool, bot: Bot, settings: Settings, interactive: bool = True) -> None:
    owner_id = settings.telegram_user_id
    if os.getenv("LORA_V2_FULL_CUTOVER", "false").lower() == "true":
        await schedule_class_alerts(pool, owner_id)
    await generate_proposals(pool, settings, owner_id)
    await queue_due_alerts(pool, owner_id)
    await send_pending_telegram(pool, bot, owner_id, interactive=interactive)


async def _delivery_loop(pool: asyncpg.Pool, bot: Bot, settings: Settings, interactive: bool) -> None:
    while True:
        try:
            await deliver_once(pool, bot, settings, interactive)
        except Exception:
            logger.exception("Notification delivery iteration failed")
        await asyncio.sleep(5)


async def run_forever(pool: asyncpg.Pool, bot: Bot, settings: Settings,
                      interactive_notifications: bool = True) -> None:
    # Model calls and Apple requests cannot hold up time-sensitive notifications.
    delivery = asyncio.create_task(_delivery_loop(pool, bot, settings, interactive_notifications))
    try:
        await _capture_loop(pool, bot, settings, interactive_notifications)
    finally:
        delivery.cancel()
        try:
            await delivery
        except asyncio.CancelledError:
            pass


async def _capture_loop(pool: asyncpg.Pool, bot: Bot, settings: Settings, interactive_notifications: bool) -> None:
    last_academic_refresh = None
    last_apple_sync = None
    while True:
        try:
            today = datetime.now(ZoneInfo(settings.timezone)).date()
            refresh = today != last_academic_refresh
            now = datetime.now(ZoneInfo(settings.timezone))
            sync_apple = (settings.apple_sync_enabled or settings.apple_events_enabled) and (
                last_apple_sync is None or (now - last_apple_sync).total_seconds() >= 300
            )
            await run_once(pool, bot, settings, refresh_academic=refresh, sync_apple=sync_apple,
                           interactive_notifications=interactive_notifications, deliver_notifications=False)
            if refresh:
                last_academic_refresh = today
            if sync_apple:
                last_apple_sync = now
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Lora v2 worker iteration failed")
        await asyncio.sleep(15)
