import json
import os
import uuid
from pathlib import Path

import pytest

from lora_v2.config import Settings
from lora_v2.db import create_pool, migrate
from lora_v2.obsidian import (
    list_schedule_conflicts, patch_document, read_document,
    resolve_schedule_conflict, safe_write, sync_vault,
)


def test_frontmatter_patch_preserves_manual_body_and_unknown_keys(tmp_path: Path) -> None:
    text = '---\ntype: schedule\nroom: "Old"\ntags: [personal, facultate]\n---\n\n# Notița mea\nText manual, [[link]] și ![[photo.png]].\n'
    updated = patch_document(text, {'room': '244', 'lora_v2_id': 'abc'})
    assert updated.split('\n---', 1)[1] == text.split('\n---', 1)[1]
    assert read_document(updated)['tags'] == ['personal', 'facultate']
    assert read_document(updated)['room'] == '244'
    path = tmp_path / 'note.md'
    path.write_text('edited concurrently')
    with pytest.raises(ValueError):
        safe_write(path, updated, text)
    assert path.read_text() == 'edited concurrently'


@pytest.mark.asyncio
async def test_obsidian_roundtrip_conflicts_and_missing_files(tmp_path: Path) -> None:
    url = os.getenv('LORA_V2_TEST_DATABASE_URL')
    if not url:
        pytest.skip('Requires isolated DB')
    owner = 909002
    cfg = Settings(database_url=url, telegram_bot_token='test', telegram_user_id=owner)
    pool = await create_pool(cfg)
    try:
        await migrate(pool)
        entity = uuid.uuid4()
        await pool.execute("""INSERT INTO academic_schedule_rules(id,owner_id,title,day_of_week,start_time,end_time,week_type,room,class_type,legacy_id)
            VALUES ($1,$2,'Test',0,'10:00','12:00','both','244','curs',900002)""", entity, owner)
        note = tmp_path / '06 Calendar' / '_Schedule' / 'original.md'
        note.parent.mkdir(parents=True)
        original = '---\ntype: schedule\nlora_id: 900002\nday_of_week: 0\nstart_time: "10:00"\nend_time: "12:00"\nweek_type: both\nroom: "244"\nclass_type: curs\n---\n# Manual\nKeep everything here.\n'
        note.write_text(original)
        archive = tmp_path / '99 Archive'
        archive.mkdir()
        (archive / 'duplicate.md').write_text(original)
        first = await sync_vault(pool, owner, tmp_path)
        assert first['conflicts'] == 0
        assert note.read_text().endswith('# Manual\nKeep everything here.\n')
        note.write_text(note.read_text().replace('room: "244"', 'room: "300"'))
        second = await sync_vault(pool, owner, tmp_path)
        assert second['imported'] == 1
        assert await pool.fetchval('SELECT room FROM academic_schedule_rules WHERE id=$1', entity) == '300'
        note.write_text(note.read_text().replace('room: "300"', 'room: "400"'))
        await pool.execute("UPDATE academic_schedule_rules SET room='500',version=version+1 WHERE id=$1", entity)
        assert (await sync_vault(pool, owner, tmp_path))['conflicts'] == 1
        assert (await sync_vault(pool, owner, tmp_path))['conflicts'] == 1
        assert 'room: "400"' in note.read_text()
        assert await pool.fetchval('SELECT room FROM academic_schedule_rules WHERE id=$1', entity) == '500'
        state = await pool.fetchval('SELECT file_fields FROM obsidian_documents WHERE entity_id=$1', entity)
        assert json.loads(state)['room'] == '300'
        conflicts = await list_schedule_conflicts(pool, owner, tmp_path)
        assert len(conflicts) == 1 and conflicts[0]['file_fields']['room'] == '400'
        with pytest.raises(ValueError, match='modificată'):
            await resolve_schedule_conflict(pool, owner, tmp_path, entity, 'keep_lora',
                                            conflicts[0]['version'], '0' * 64)
        await resolve_schedule_conflict(pool, owner, tmp_path, entity, 'keep_lora',
                                        conflicts[0]['version'], conflicts[0]['file_revision'])
        assert read_document(note.read_text())['room'] == '500'
        assert (await sync_vault(pool, owner, tmp_path))['conflicts'] == 0
        note.write_text(note.read_text().replace('room: "500"', 'room: "600"'))
        await pool.execute("UPDATE academic_schedule_rules SET room='700',version=version+1 WHERE id=$1", entity)
        assert (await sync_vault(pool, owner, tmp_path))['conflicts'] == 1
        conflict = (await list_schedule_conflicts(pool, owner, tmp_path))[0]
        await resolve_schedule_conflict(pool, owner, tmp_path, entity, 'use_obsidian',
                                        conflict['version'], conflict['file_revision'])
        assert await pool.fetchval('SELECT room FROM academic_schedule_rules WHERE id=$1', entity) == '600'
        assert (await sync_vault(pool, owner, tmp_path))['conflicts'] == 0
        note.unlink()
        assert (await sync_vault(pool, owner, tmp_path))['conflicts'] == 1
        assert not note.exists()
        assert (archive / 'duplicate.md').read_text() == original
    finally:
        await pool.close()


@pytest.mark.asyncio
async def test_slow_model_does_not_block_notification_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    import asyncio
    from lora_v2 import worker
    delivered = asyncio.Event()
    blocked = asyncio.Event()

    async def slow_capture(*args: object, **kwargs: object) -> None:
        await blocked.wait()

    async def deliver(*args: object, **kwargs: object) -> None:
        delivered.set()

    monkeypatch.setattr(worker, '_capture_loop', slow_capture)
    monkeypatch.setattr(worker, 'deliver_once', deliver)
    task = asyncio.create_task(worker.run_forever(None, None, None))
    try:
        await asyncio.wait_for(delivered.wait(), timeout=1)
        assert not task.done()
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task


@pytest.mark.asyncio
async def test_command_reply_retries_after_network_error_without_duplicate_rows() -> None:
    from datetime import datetime, timedelta, timezone
    from lora_v2.notifications import queue_reply, send_pending_telegram
    url = os.getenv('LORA_V2_TEST_DATABASE_URL')
    if not url:
        pytest.skip('Requires isolated DB')
    owner = 909004
    pool = await create_pool(Settings(database_url=url, telegram_bot_token='test', telegram_user_id=owner))

    class Transport:
        failed = False
        delivered: list[str] = []

        async def send_message(self, **kwargs: object) -> None:
            if not self.failed:
                self.failed = True
                raise ConnectionError('Simulated TLS connection failure')
            self.delivered.append(str(kwargs['text']))

    bot = Transport()
    try:
        await migrate(pool)
        await queue_reply(pool, owner, 'update-123', 'Programul de azi')
        await queue_reply(pool, owner, 'update-123', 'Programul de azi')
        now = datetime.now(timezone.utc)
        assert await send_pending_telegram(pool, bot, owner, now=now) == 0
        assert await pool.fetchval("SELECT status FROM notification_outbox WHERE owner_id=$1", owner) == 'pending'
        assert await send_pending_telegram(pool, bot, owner, now=now + timedelta(seconds=10)) == 1
        assert await send_pending_telegram(pool, bot, owner, now=now + timedelta(seconds=20)) == 0
        assert bot.delivered == ['Programul de azi']
    finally:
        await pool.close()
