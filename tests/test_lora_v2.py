"""Lora v2 contract checks; DB journey runs only against an isolated test URL."""

import hashlib
import hmac
import json
import os
import time
import uuid
import io
from datetime import datetime
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

import pytest
from fastapi import HTTPException
from PIL import Image

from lora_v2.auth import verify_init_data
from lora_v2.academic_calendar import _week_type, materialize_schedule
from lora_v2.config import Settings
from lora_v2.crud import EditRequest, update_entity
from lora_v2.db import create_pool, migrate
from lora_v2.models import Command
from lora_v2.media import save_photo
from lora_v2.agent import Candidate
from lora_v2.grounding import grounding_issue
from lora_v2.apple import _digest, pull_changes, push_pending
from lora_v2.notifications import queue_due_alerts
from lora_v2.rules import extract_common
from lora_v2.processor import process_capture
from lora_v2.proactive import decide_proposal, generate_proposals
from lora_v2.service import capture, execute_command


def _settings(database_url: str = "postgresql://localhost/lora_v2_test") -> Settings:
    return Settings(database_url=database_url, telegram_bot_token="test-token", telegram_user_id=123)


def _init_data(token: str, user_id: int, auth_date: int) -> str:
    values = {"auth_date": str(auth_date), "user": json.dumps({"id": user_id}, separators=(",", ":"))}
    check = "\n".join(f"{key}={value}" for key, value in sorted(values.items()))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    values["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(values)


def test_telegram_identity_is_verified_and_expires():
    now = int(time.time())
    assert verify_init_data(_init_data("test-token", 123, now), _settings(), now=now) == 123
    with pytest.raises(HTTPException) as wrong_user:
        verify_init_data(_init_data("test-token", 124, now), _settings(), now=now)
    assert wrong_user.value.status_code == 403
    with pytest.raises(HTTPException) as expired:
        verify_init_data(_init_data("test-token", 123, now - 86401), _settings(), now=now)
    assert expired.value.status_code == 401


def test_commands_require_timezone_and_known_type():
    with pytest.raises(ValueError):
        Command(type="create_calendar_entry", data={
            "kind": "reminder", "title": "Sună", "starts_at": "2026-10-15T12:00:00",
        }).payload()
    with pytest.raises(ValueError):
        Command(type="arbitrary_sql", data={}).payload()


def test_academic_week_parity_skips_full_vacation():
    from datetime import date

    semester = date(2026, 9, 28)
    assert _week_type(date(2026, 9, 28), semester, []) == "odd"
    assert _week_type(date(2026, 10, 5), semester, []) == "even"
    assert _week_type(date(2026, 10, 12), semester, [(date(2026, 10, 5), date(2026, 10, 11))]) == "even"


def test_photo_is_normalized_into_private_local_storage(tmp_path):
    settings = Settings(database_url="test", telegram_bot_token="test", telegram_user_id=123,
                        media_dir=str(tmp_path))
    buffer = io.BytesIO()
    Image.new("RGB", (32, 24), color="pink").save(buffer, format="PNG")
    path = save_photo(settings, buffer.getvalue())
    assert path.endswith(".jpg")
    assert os.stat(path).st_mode & 0o077 == 0
    with Image.open(path) as converted:
        assert converted.size == (32, 24)
    with pytest.raises(ValueError):
        save_photo(settings, b"x" * (10 * 1024 * 1024 + 1))


def test_ai_dates_and_amounts_must_match_message():
    now = datetime(2026, 10, 14, 12, tzinfo=ZoneInfo("Europe/Bucharest"))
    football = Candidate(type="create_calendar_entry", title="Meci", kind="event",
                         starts_at="2026-10-15T19:30:00+03:00", confidence=1)
    assert grounding_issue(football, "Duminică am meci de la 20", _settings(), now)
    expense = Candidate(type="log_expense", amount=50, confidence=1)
    assert grounding_issue(expense, "Am dat 15 lei la cantină", _settings(), now)


def test_compound_daily_message_uses_grounded_shortcuts():
    now = datetime(2026, 10, 14, 12, tzinfo=ZoneInfo("Europe/Bucharest"))
    message = (
        "Mâine trebuie să sun la administrator pe la amiaza; dacă nu îl sun, poimâine. "
        "Duminică am meci de fotbal de la 20. "
        "Azi am mâncat la cantină de 15 lei piept de pui și piure. "
        "Am mers la sală să fac antrenament de piept timp de 45 de minute."
    )
    result, remaining = extract_common(message, now, "Europe/Bucharest")
    assert remaining == ""
    assert [item.type for item in result.actions] == [
        "create_calendar_entry", "create_calendar_entry", "log_expense", "log_meal", "log_workout",
    ]
    assert result.actions[0].starts_at == "2026-10-15T12:00:00+03:00"
    assert result.actions[0].confidence < 0.85
    assert result.actions[1].starts_at == "2026-10-18T20:00:00+03:00"
    assert result.actions[1].alert_offsets_minutes == [30, 0]
    assert result.actions[2].amount == 15
    assert result.actions[4].duration_minutes == 45
    assert "12:00" in (result.actions[0].missing_information or "")


@pytest.mark.asyncio
async def test_v2_database_journey():
    url = os.getenv("LORA_V2_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set LORA_V2_TEST_DATABASE_URL to an isolated test database")
    assert url != os.getenv("DATABASE_URL"), "Test DB must not be the legacy DB"
    settings = _settings(url)
    owner = uuid.uuid4().int % 1000000000
    pool = await create_pool(settings)
    try:
        await migrate(pool)
        local = ZoneInfo(settings.timezone)
        now = datetime.now(local).replace(hour=20, minute=1, second=0, microsecond=0)
        target = now.replace(hour=12, minute=0)
        capture_row = await capture(pool, owner, "test", str(uuid.uuid4()), "Sună administratorul")
        reminder = Command(type="create_calendar_entry", data={
            "kind": "reminder", "title": "Sună administratorul",
            "starts_at": target.isoformat(), "alert_offsets_minutes": [0],
            "followup_evening": True,
        })
        key = str(uuid.uuid4())
        first = await execute_command(pool, settings, owner, reminder, key, capture_row["id"])
        repeat = await execute_command(pool, settings, owner, reminder, key, capture_row["id"])
        assert first.status == "saved" and repeat.status == "already_done"
        assert await generate_proposals(pool, settings, owner, now) == 1
        async with pool.acquire() as conn:
            proposal_id = await conn.fetchval(
                "SELECT id FROM proposals WHERE owner_id=$1 AND source LIKE 'followup:%'", owner
            )
        assert proposal_id
        decision = await decide_proposal(pool, settings, owner, proposal_id, True)
        assert decision and decision.status == "saved"
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT starts_at,version FROM calendar_entries WHERE id=$1",
                uuid.UUID(first.entity_id),
            )
            count = await conn.fetchval(
                "SELECT count(*) FROM calendar_entries WHERE owner_id=$1", owner
            )
        assert row["starts_at"].date() > target.date() and row["version"] == 2
        assert count == 1

        merchant = "Cantina " + str(uuid.uuid4())[:8]
        expense = Command(type="log_expense", data={
            "amount": "15", "category": "altele", "merchant": merchant,
            "spent_at": now.isoformat(),
        })
        original = await execute_command(pool, settings, owner, expense, str(uuid.uuid4()))
        updated = await update_entity(pool, settings, owner, "expense", uuid.UUID(original.entity_id), EditRequest(
            expected_version=1,
            data={"amount": "15", "category": "mâncare", "merchant": merchant, "spent_at": now.isoformat()},
        ))
        assert updated.status == "saved"
        again = await execute_command(pool, settings, owner, expense, str(uuid.uuid4()))
        async with pool.acquire() as conn:
            learned = await conn.fetchval("SELECT category FROM expenses WHERE id=$1", uuid.UUID(again.entity_id))
        assert learned == "mâncare"

        due_task = await execute_command(pool, settings, owner, Command(type="create_task", data={
            "title": "Trimite proiectul", "due_at": now.isoformat(),
        }), str(uuid.uuid4()))
        assert due_task.status == "saved"
        assert await queue_due_alerts(pool, owner, now) >= 1
        async with pool.acquire() as conn:
            task_alerts = await conn.fetchval(
                "SELECT count(*) FROM notification_outbox WHERE owner_id=$1 AND kind='task_alert'",
                owner,
            )
        assert task_alerts == 1

        from datetime import timedelta
        beginning = now.date()
        monday = beginning - timedelta(days=beginning.weekday())
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO academic_semesters(owner_id,semester_start) VALUES ($1,$2)", owner, monday
            )
            rule_id = uuid.uuid4()
            await conn.execute(
                """INSERT INTO academic_schedule_rules(id,owner_id,title,day_of_week,start_time,end_time,week_type,class_type)
                VALUES ($1,$2,'Analiză financiară',0,'10:00','12:00','both','curs')""",
                rule_id, owner,
            )
        count = await materialize_schedule(pool, settings, owner, start=monday, days=7)
        repeat_count = await materialize_schedule(pool, settings, owner, start=monday, days=7)
        async with pool.acquire() as conn:
            academic_count = await conn.fetchval(
                "SELECT count(*) FROM calendar_entries WHERE owner_id=$1 AND kind='academic'", owner
            )
        assert count == 1 and repeat_count == 0 and academic_count == 1
        async with pool.acquire() as conn:
            await conn.execute("UPDATE academic_schedule_rules SET is_active=false WHERE id=$1", rule_id)
        await materialize_schedule(pool, settings, owner, start=monday, days=7)
        async with pool.acquire() as conn:
            active_count = await conn.fetchval(
                "SELECT count(*) FROM calendar_entries WHERE owner_id=$1 AND kind='academic' AND status='active'",
                owner,
            )
        assert active_count == 0
    finally:
        await pool.close()


@pytest.mark.asyncio
async def test_apple_two_way_sync_and_conflict(monkeypatch):
    url = os.getenv("LORA_V2_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set LORA_V2_TEST_DATABASE_URL to an isolated test database")
    settings = Settings(database_url=url, telegram_bot_token="test", telegram_user_id=123,
                        icloud_username="fake", icloud_app_password="fake", apple_sync_enabled=True)
    owner = uuid.uuid4().int % 1000000000
    remote_data = {}

    class FakeRemote:
        def __init__(self, _settings):
            pass

        def get_revision(self, uid):
            return remote_data[uid][0] if uid in remote_data else None

        def upsert(self, uid, title, due, completed):
            revision = _digest(title, due, completed)
            remote_data[uid] = (revision, title, due, completed)
            return revision

        def delete(self, uid):
            remote_data.pop(uid, None)

        def list_all(self):
            return [(uid, *data) for uid, data in remote_data.items()]

    monkeypatch.setattr("lora_v2.apple.AppleRemote", FakeRemote)
    pool = await create_pool(settings)
    try:
        await migrate(pool)
        created = await execute_command(pool, settings, owner,
            Command(type="create_task", data={"title": "Sună administratorul"}), str(uuid.uuid4()))
        assert await push_pending(pool, settings, owner) == 1
        uid = f"lora-v2-task-{created.entity_id}@lora"
        assert uid in remote_data
        edited_title = "Sună administratorul blocului"
        remote_data[uid] = (_digest(edited_title, None, False), edited_title, None, False)
        changes = await pull_changes(pool, settings, owner)
        assert changes["updated"] == 1
        async with pool.acquire() as conn:
            title = await conn.fetchval("SELECT title FROM tasks WHERE id=$1", uuid.UUID(created.entity_id))
        assert title == edited_title

        imported_uid = "apple-external-task-1"
        remote_data[imported_uid] = (_digest("Task din Apple", None, False), "Task din Apple", None, False)
        changes = await pull_changes(pool, settings, owner)
        assert changes["imported"] == 1
        async with pool.acquire() as conn:
            imported_id = await conn.fetchval(
                "SELECT entity_id FROM apple_links WHERE owner_id=$1 AND apple_uid=$2",
                owner, imported_uid,
            )
        changed = await update_entity(pool, settings, owner, "task", imported_id,
                                      EditRequest(expected_version=1, data={"title": "Task modificat local"}))
        assert changed.status == "saved"
        assert await push_pending(pool, settings, owner) == 1
        assert remote_data[imported_uid][1] == "Task modificat local"

        async with pool.acquire() as conn:
            await conn.execute("UPDATE tasks SET title='Modificare locală',version=version+1 WHERE id=$1",
                               uuid.UUID(created.entity_id))
        remote_data[uid] = (_digest("Modificare Apple", None, False), "Modificare Apple", None, False)
        changes = await pull_changes(pool, settings, owner)
        assert changes["conflicts"] == 1
        async with pool.acquire() as conn:
            title = await conn.fetchval("SELECT title FROM tasks WHERE id=$1", uuid.UUID(created.entity_id))
        assert title == "Modificare locală"
    finally:
        await pool.close()


@pytest.mark.asyncio
async def test_compound_capture_saves_clear_facts_and_asks_for_ambiguous_time():
    url = os.getenv("LORA_V2_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set LORA_V2_TEST_DATABASE_URL to an isolated test database")
    settings = _settings(url)
    owner = uuid.uuid4().int % 1000000000
    message = (
        "Mâine trebuie să sun la administrator pe la amiaza; dacă nu îl sun, poimâine. "
        "Duminică am meci de fotbal de la 20. "
        "Azi am mâncat la cantină de 15 lei piept de pui și piure. "
        "Am mers la sală să fac antrenament de piept timp de 45 de minute."
    )
    pool = await create_pool(settings)
    try:
        await migrate(pool)
        row = await capture(pool, owner, "test", str(uuid.uuid4()), message)
        results = await process_capture(pool, settings, owner, row["id"])
        assert sum(result.status == "saved" for result in results) == 4
        async with pool.acquire() as conn:
            counts = [
                await conn.fetchval("SELECT count(*) FROM proposals WHERE owner_id=$1", owner),
                await conn.fetchval("SELECT count(*) FROM calendar_entries WHERE owner_id=$1", owner),
                await conn.fetchval("SELECT count(*) FROM expenses WHERE owner_id=$1", owner),
                await conn.fetchval("SELECT count(*) FROM meals WHERE owner_id=$1", owner),
                await conn.fetchval("SELECT count(*) FROM workouts WHERE owner_id=$1", owner),
            ]
        assert counts == [1, 1, 1, 1, 1]
    finally:
        await pool.close()
