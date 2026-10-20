"""Isolated Apple Calendar event sync contract."""

import os
import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from lora_v2 import apple_events
from lora_v2.config import Settings
from lora_v2.crud import delete_entity, update_entity, EditRequest
from lora_v2.db import create_pool, migrate
from lora_v2.models import Command
from lora_v2.service import execute_command


@pytest.mark.asyncio
async def test_v2_event_sync_does_not_overwrite_remote_edit(monkeypatch: pytest.MonkeyPatch) -> None:
    url = os.getenv('LORA_V2_TEST_DATABASE_URL')
    if not url:
        pytest.skip('Requires isolated database')
    owner = uuid.uuid4().int % 1000000000
    settings = Settings(database_url=url, telegram_bot_token='test', telegram_user_id=owner,
                        apple_events_enabled=True, icloud_username='test', icloud_app_password='test')
    pool = await create_pool(settings)
    revisions: dict[str, str] = {}
    received_offsets: list[list[int]] = []

    class FakeRemote:
        def __init__(self, _settings: Settings):
            pass

        def get_revision(self, uid: str) -> str | None:
            return revisions.get(uid)

        def get_snapshot(self, uid: str) -> dict[str, object] | None:
            if uid not in revisions:
                return None
            return {'title': 'Fotbal Apple', 'starts_at': begins + timedelta(hours=1),
                    'ends_at': begins + timedelta(hours=2), 'notes': 'Mutat în Apple',
                    'revision': revisions[uid]}

        def upsert(self, uid: str, title: str, start: datetime, end: datetime,
                   notes: str | None, offsets: list[int]) -> str:
            received_offsets.append(offsets)
            revisions[uid] = apple_events._revision(title, start, end, notes)
            return revisions[uid]

        def delete(self, uid: str) -> None:
            revisions.pop(uid, None)

    monkeypatch.setattr(apple_events, 'AppleEventRemote', FakeRemote)
    try:
        await migrate(pool)
        begins = datetime.now(ZoneInfo('Europe/Bucharest')) + timedelta(days=2)
        result = await execute_command(pool, settings, owner, Command(type='create_calendar_entry', data={
            'kind': 'event', 'title': 'Fotbal', 'starts_at': begins.isoformat(),
            'alert_offsets_minutes': [30, 0],
        }), str(uuid.uuid4()))
        entity_id = uuid.UUID(result.entity_id)
        assert (await apple_events.sync_events(pool, settings, owner))['synced'] == 1
        assert received_offsets == [[0, 30]]
        assert (await apple_events.sync_events(pool, settings, owner))['synced'] == 0
        uid = next(iter(revisions))
        edited = await update_entity(pool, settings, owner, 'calendar_entry', entity_id,
                                     EditRequest(expected_version=1, data={
                                         'kind': 'event', 'title': 'Fotbal cu prietenii',
                                         'starts_at': begins.isoformat(), 'alert_offsets_minutes': [30, 0],
                                     }))
        assert edited.status == 'saved'
        saved_revision = revisions[uid]
        revisions[uid] = 'changed-in-apple'
        assert (await apple_events.sync_events(pool, settings, owner))['conflicts'] == 1
        assert revisions[uid] == 'changed-in-apple'
        pending = await pool.fetchrow(
            'SELECT status,local_version FROM apple_event_conflicts WHERE owner_id=$1 AND entity_id=$2',
            owner, entity_id,
        )
        assert pending['status'] == 'pending' and pending['local_version'] == 2
        message = await apple_events.resolve_event_conflict(pool, settings, owner,
                                                            entity_id, 'use_apple', 2)
        assert 'Apple Calendar' in message
        accepted = await pool.fetchrow(
            'SELECT title,starts_at,version FROM calendar_entries WHERE owner_id=$1 AND id=$2',
            owner, entity_id,
        )
        assert accepted['title'] == 'Fotbal Apple' and accepted['version'] == 3
        assert accepted['starts_at'] == begins + timedelta(hours=1)
        assert await pool.fetchval(
            'SELECT status FROM apple_event_conflicts WHERE owner_id=$1 AND entity_id=$2',
            owner, entity_id,
        ) == 'resolved'
        revisions[uid] = saved_revision
        edited_again = await update_entity(pool, settings, owner, 'calendar_entry', entity_id,
                                           EditRequest(expected_version=3, data={
                                               'kind': 'event', 'title': 'Fotbal nou',
                                               'starts_at': begins.isoformat(),
                                           }))
        assert edited_again.status == 'saved'
        assert (await apple_events.sync_events(pool, settings, owner))['conflicts'] == 1
        await apple_events.resolve_event_conflict(pool, settings, owner, entity_id, 'keep_lora', 4)
        assert (await apple_events.sync_events(pool, settings, owner))['synced'] == 1
        deleted = await delete_entity(pool, owner, 'calendar_entry', entity_id, 4)
        assert deleted.status == 'saved'
        assert (await apple_events.sync_events(pool, settings, owner))['synced'] == 1
        assert uid not in revisions
    finally:
        await pool.close()
