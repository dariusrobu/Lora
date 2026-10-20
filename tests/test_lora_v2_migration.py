"""Cutover must preserve source details, user edits, and notification ownership."""

import json
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from lora_v2.config import Settings
from lora_v2.db import create_pool, migrate
from lora_v2.legacy_snapshot import save_snapshot
from lora_v2.migrate_legacy import QUERIES, import_legacy


@pytest.mark.asyncio
async def test_full_snapshot_refresh_and_no_duplicate_notifications() -> None:
    url = os.getenv("LORA_V2_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Requires isolated LORA_V2_TEST_DATABASE_URL")
    settings = Settings(database_url=url, telegram_bot_token="test", telegram_user_id=909001)
    pool = await create_pool(settings)
    try:
        await migrate(pool)
        source = {"journal_entries": [{"id": 1, "content": "Notă personală", "extra": {"keep": True}}], "empty_table": []}
        snapshot_id = await save_snapshot(pool, settings.telegram_user_id, source)
        rows = await pool.fetch("SELECT table_name,rows FROM legacy_snapshot_tables WHERE snapshot_id=$1", snapshot_id)
        assert {r["table_name"]: json.loads(r["rows"]) for r in rows} == source
        tomorrow = datetime.now(ZoneInfo(settings.timezone)) + timedelta(days=1)
        data = {key: [] for key in QUERIES}
        data["events"] = [{"id": 900001, "event_date": tomorrow.date(), "event_time": tomorrow.time().replace(tzinfo=None), "title": "Reminder inițial", "event_type": "reminder"}]
        await import_legacy(pool, settings, settings.telegram_user_id, data, schedule_alerts=False)
        assert await pool.fetchval("SELECT count(*) FROM alert_occurrences WHERE owner_id=$1", settings.telegram_user_id) == 0
        data["events"][0]["title"] = "Corectat în versiunea veche"
        await import_legacy(pool, settings, settings.telegram_user_id, data, schedule_alerts=False)
        assert await pool.fetchval("SELECT title FROM calendar_entries WHERE owner_id=$1 AND legacy_id=900001", settings.telegram_user_id) == "Corectat în versiunea veche"
        await pool.execute("UPDATE calendar_entries SET title='Editat în v2',version=2 WHERE owner_id=$1", settings.telegram_user_id)
        await import_legacy(pool, settings, settings.telegram_user_id, data)
        assert await pool.fetchval("SELECT title FROM calendar_entries WHERE owner_id=$1 AND legacy_id=900001", settings.telegram_user_id) == "Editat în v2"
        assert await pool.fetchval("SELECT count(*) FROM alert_occurrences WHERE owner_id=$1", settings.telegram_user_id) == 0
    finally:
        await pool.close()
