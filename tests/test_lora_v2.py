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
from lora_v2.crud import EditRequest, delete_entity, update_entity
from lora_v2.db import create_pool, migrate
from lora_v2.models import Command
from lora_v2.media import save_photo
from lora_v2.agent import Candidate, parse_interpretation
from lora_v2.grounding import grounding_issue
from lora_v2.apple import _digest, pull_changes, push_pending, resolve_conflict
from lora_v2.notifications import queue_due_alerts, send_pending_telegram
from lora_v2.rules import extract_common
from lora_v2.processor import process_capture
from lora_v2.academics import delete_academic, list_academics, set_semester, write_academic
from lora_v2.proactive import decide_followup, generate_proposals
from lora_v2.queries import answer_read_intent, read_intent
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


def test_health_shortcuts_extract_water_and_weight():
    now = datetime(2026, 10, 14, 12, tzinfo=ZoneInfo("Europe/Bucharest"))
    result, remaining = extract_common("Azi am băut 500 ml apă și cântăresc 78,5 kg.", now, "Europe/Bucharest")
    assert remaining == ""
    assert len(result.actions) == 1
    assert result.actions[0].type == "log_health"
    assert result.actions[0].water_ml_delta == 500
    assert result.actions[0].weight_kg == 78.5


def test_common_daily_phrases_are_grounded_without_model_dates():
    now = datetime(2026, 10, 14, 15, tzinfo=ZoneInfo("Europe/Bucharest"))
    task, left = extract_common("Mâine la 9 trebuie să trimit proiectul la statistică.", now, "Europe/Bucharest")
    assert left == "" and task.actions[0].type == "create_task"
    assert task.actions[0].due_at == "2026-10-15T09:00:00+03:00"
    reminder, left = extract_common("Adu-mi aminte luni la 16 să predau tema.", now, "Europe/Bucharest")
    assert left == "" and reminder.actions[0].type == "create_calendar_entry"
    assert reminder.actions[0].starts_at == "2026-10-19T16:00:00+03:00"
    expense, left = extract_common("Am plătit azi 38 lei pe Bolt.", now, "Europe/Bucharest")
    assert left == "" and expense.actions[0].category == "transport"
    meal, left = extract_common("Azi am mâncat 200 g piept de pui și 150 g orez.", now, "Europe/Bucharest")
    assert left == "" and len(meal.actions[0].items) == 2
    assert meal.actions[0].items[1].grams == 150
    assert meal.actions[0].confidence < 0.85
    health, left = extract_common("Astăzi am dormit 7 ore și am băut un litru de apă.", now, "Europe/Bucharest")
    assert left == "" and health.actions[0].water_ml_delta == 1000


def test_income_shortcut_is_distinct_from_expense():
    now = datetime(2026, 10, 14, 12, tzinfo=ZoneInfo("Europe/Bucharest"))
    result, remaining = extract_common("Azi am primit 100 lei.", now, "Europe/Bucharest")
    assert remaining == ""
    assert [item.type for item in result.actions] == ["log_income"]


def test_read_questions_do_not_intercept_writes():
    assert read_intent("Ce am azi?") == "today"
    assert read_intent("Ce trebuie să fac?") == "tasks"
    assert read_intent("Cât am cheltuit luna asta?") == "expenses"
    assert read_intent("Adu-mi aminte mâine să sun") is None
    assert read_intent("Azi am cheltuit 15 lei") is None


def test_invalid_local_model_action_does_not_discard_valid_actions():
    result = parse_interpretation(json.dumps({"actions": [
        {"type": "create_deadline", "title": "Tema"},
        {"type": "log_expense", "amount": 15, "confidence": 0.95},
    ], "reply": None}))
    assert [item.type for item in result.actions] == ["log_expense"]
    assert "Nu am înțeles" in result.reply
    assert parse_interpretation("{broken").actions == []


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
        sent_messages = []

        class FakeBot:
            async def send_message(self, **kwargs):
                sent_messages.append(kwargs)

        await send_pending_telegram(pool, FakeBot(), owner)
        followup_message = next(item for item in sent_messages if "Ai reușit" in item["text"])
        labels = [button.text for button in followup_message["reply_markup"].inline_keyboard[0]]
        assert labels == ["Am făcut", "Mută pe mâine"]
        decision = await decide_followup(pool, settings, owner, proposal_id, "tomorrow")
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

        done_reminder = await execute_command(pool, settings, owner, Command(type="create_calendar_entry", data={
            "kind": "reminder", "title": "Sună la recepție", "starts_at": target.isoformat(),
            "followup_evening": True,
        }), str(uuid.uuid4()))
        assert done_reminder.status == "saved"
        assert await generate_proposals(pool, settings, owner, now) == 1
        async with pool.acquire() as conn:
            done_proposal = await conn.fetchval(
                "SELECT id FROM proposals WHERE owner_id=$1 AND source=$2",
                owner, f"followup:{done_reminder.entity_id}:v1",
            )
        assert done_proposal
        completed = await decide_followup(pool, settings, owner, done_proposal, "done")
        assert completed and completed.status == "saved"
        async with pool.acquire() as conn:
            done_status = await conn.fetchval(
                "SELECT status FROM calendar_entries WHERE id=$1", uuid.UUID(done_reminder.entity_id),
            )
        assert done_status == "done"

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
        manual = await execute_command(pool, settings, owner, Command(type="log_expense", data={
            "amount": "20", "category": "cadouri", "category_override": True,
            "merchant": merchant, "spent_at": now.isoformat(),
        }), str(uuid.uuid4()))
        async with pool.acquire() as conn:
            manual_category = await conn.fetchval(
                "SELECT category FROM expenses WHERE id=$1", uuid.UUID(manual.entity_id),
            )
        assert manual_category == "cadouri"
        learned_again = await execute_command(pool, settings, owner, expense, str(uuid.uuid4()))
        async with pool.acquire() as conn:
            latest_category = await conn.fetchval(
                "SELECT category FROM expenses WHERE id=$1", uuid.UUID(learned_again.entity_id),
            )
        assert latest_category == "cadouri"

        due_task = await execute_command(pool, settings, owner, Command(type="create_task", data={
            "title": "Trimite proiectul", "due_at": now.isoformat(),
        }), str(uuid.uuid4()))
        assert due_task.status == "saved"
        today_answer = await answer_read_intent(pool, settings, owner, "today", now)
        assert "Trimite proiectul" in today_answer and "Sună administratorul" not in today_answer
        tasks_answer = await answer_read_intent(pool, settings, owner, "tasks", now)
        assert "Trimite proiectul" in tasks_answer
        assert await queue_due_alerts(pool, owner, now) >= 1
        async with pool.acquire() as conn:
            task_alerts = await conn.fetchval(
                "SELECT count(*) FROM notification_outbox WHERE owner_id=$1 AND kind='task_alert'",
                owner,
            )
        assert task_alerts == 1

        health_one = await execute_command(pool, settings, owner, Command(type="log_health", data={
            "log_date": now.date().isoformat(), "water_ml_delta": 500,
        }), str(uuid.uuid4()))
        health_two = await execute_command(pool, settings, owner, Command(type="log_health", data={
            "log_date": now.date().isoformat(), "water_ml_delta": 250,
        }), str(uuid.uuid4()))
        assert health_one.entity_id == health_two.entity_id
        async with pool.acquire() as conn:
            water = await conn.fetchval("SELECT water_ml FROM health_entries WHERE id=$1", uuid.UUID(health_one.entity_id))
        assert water == 750
        edited_health = await update_entity(pool, settings, owner, "health", uuid.UUID(health_one.entity_id),
            EditRequest(expected_version=2, data={"log_date": now.date().isoformat(), "water_ml": 1000}))
        assert edited_health.status == "saved"
        deleted_health = await delete_entity(pool, owner, "health", uuid.UUID(health_one.entity_id), 3)
        assert deleted_health.status == "saved"

        workout = await execute_command(pool, settings, owner, Command(type="log_workout", data={
            "activity": "Piept", "started_at": now.isoformat(), "duration_minutes": 45,
            "exercises": [{"name": "Împins la piept", "sets": 3, "reps": 8, "weight_kg": "60"}],
        }), str(uuid.uuid4()))
        async with pool.acquire() as conn:
            exercise = await conn.fetchrow(
                "SELECT name,sets,reps,weight_kg FROM workout_exercises WHERE workout_id=$1",
                uuid.UUID(workout.entity_id),
            )
        assert exercise["sets"] == 3 and exercise["reps"] == 8
        changed_workout = await update_entity(pool, settings, owner, "workout", uuid.UUID(workout.entity_id),
            EditRequest(expected_version=1, data={
                "activity": "Piept", "started_at": now.isoformat(), "duration_minutes": 45,
                "exercises": [{"name": "Împins la piept", "sets": 4, "reps": 8, "weight_kg": "60"}],
            }))
        assert changed_workout.status == "saved"
        async with pool.acquire() as conn:
            exercise_count = await conn.fetchval(
                "SELECT count(*) FROM workout_exercises WHERE workout_id=$1",
                uuid.UUID(workout.entity_id),
            )
        assert exercise_count == 1

        income = await execute_command(pool, settings, owner, Command(type="log_income", data={
            "amount": "100", "currency": "RON", "source": "Test", "received_at": now.isoformat(),
        }), str(uuid.uuid4()))
        assert income.status == "saved"
        changed_income = await update_entity(pool, settings, owner, "income", uuid.UUID(income.entity_id),
            EditRequest(expected_version=1, data={
                "amount": "120", "currency": "RON", "source": "Test", "received_at": now.isoformat(),
            }))
        assert changed_income.status == "saved"

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
            conflict_id = await conn.fetchval(
                "SELECT id FROM apple_sync_conflicts WHERE owner_id=$1 AND entity_id=$2 AND status='pending'",
                owner, uuid.UUID(created.entity_id),
            )
        assert title == "Modificare locală"
        assert await resolve_conflict(pool, settings, owner, conflict_id, "keep_local")
        assert await push_pending(pool, settings, owner) == 1
        assert remote_data[uid][1] == "Modificare locală"

        async with pool.acquire() as conn:
            await conn.execute("UPDATE tasks SET title='Altă schimbare locală',version=version+1 WHERE id=$1",
                               uuid.UUID(created.entity_id))
        remote_data[uid] = (_digest("Altă schimbare Apple", None, False), "Altă schimbare Apple", None, False)
        assert (await pull_changes(pool, settings, owner))["conflicts"] == 1
        async with pool.acquire() as conn:
            conflict_id = await conn.fetchval(
                "SELECT id FROM apple_sync_conflicts WHERE owner_id=$1 AND entity_id=$2 AND status='pending'",
                owner, uuid.UUID(created.entity_id),
            )
        assert await resolve_conflict(pool, settings, owner, conflict_id, "use_apple")
        async with pool.acquire() as conn:
            title = await conn.fetchval("SELECT title FROM tasks WHERE id=$1", uuid.UUID(created.entity_id))
        assert title == "Altă schimbare Apple"
        remote_data.pop(uid)
        await pull_changes(pool, settings, owner)
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE apple_links SET missing_since=now()-interval '6 minutes' WHERE owner_id=$1 AND apple_uid=$2",
                owner, uid,
            )
        assert (await pull_changes(pool, settings, owner))["conflicts"] == 1
        async with pool.acquire() as conn:
            conflict_id = await conn.fetchval(
                "SELECT id FROM apple_sync_conflicts WHERE owner_id=$1 AND entity_id=$2 AND status='pending'",
                owner, uuid.UUID(created.entity_id),
            )
        assert await resolve_conflict(pool, settings, owner, conflict_id, "use_apple")
        async with pool.acquire() as conn:
            status = await conn.fetchval("SELECT status FROM tasks WHERE id=$1", uuid.UUID(created.entity_id))
            link = await conn.fetchval("SELECT 1 FROM apple_links WHERE owner_id=$1 AND apple_uid=$2", owner, uid)
        assert status == "cancelled" and link is None
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


@pytest.mark.asyncio
async def test_university_records_and_calendar_are_editable():
    url = os.getenv("LORA_V2_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set LORA_V2_TEST_DATABASE_URL to an isolated test database")
    settings = _settings(url)
    owner = uuid.uuid4().int % 1000000000
    pool = await create_pool(settings)
    try:
        await migrate(pool)
        from datetime import timedelta
        today = datetime.now(ZoneInfo(settings.timezone)).date()
        monday = today - timedelta(days=today.weekday())
        await set_semester(pool, owner, monday, monday + timedelta(days=90), None)
        subject = await write_academic(pool, owner, "subject", {"name": "Analiză financiară", "credits": 5})
        rule = await write_academic(pool, owner, "schedule", {
            "title": "Analiză financiară", "subject_id": subject["id"],
            "day_of_week": today.weekday(), "start_time": "10:00", "end_time": "12:00",
            "class_type": "curs",
        })
        exam = await write_academic(pool, owner, "exam", {
            "title": "Analiză financiară", "subject_id": subject["id"],
            "starts_at": datetime.now(ZoneInfo(settings.timezone)).isoformat(),
        })
        await write_academic(pool, owner, "attendance", {
            "subject_id": subject["id"], "schedule_rule_id": rule["id"],
            "class_date": today.isoformat(), "attended": True,
        })
        await write_academic(pool, owner, "grade", {
            "subject_id": subject["id"], "label": "parțial", "value": "9.5",
        })
        count = await materialize_schedule(pool, settings, owner, start=today, days=1)
        assert count == 2
        listed = await list_academics(pool, owner)
        assert len(listed["subjects"]) == len(listed["attendance"]) == len(listed["grades"]) == 1
        await delete_academic(pool, owner, "schedule", uuid.UUID(rule["id"]), rule["version"])
        await delete_academic(pool, owner, "exam", uuid.UUID(exam["id"]), exam["version"])
        await materialize_schedule(pool, settings, owner, start=today, days=1)
        async with pool.acquire() as conn:
            active = await conn.fetchval(
                "SELECT count(*) FROM calendar_entries WHERE owner_id=$1 AND kind='academic' AND status='active'",
                owner,
            )
        assert active == 0
    finally:
        await pool.close()
