"""Daily agent plans must stay grounded, deduplicated and approval-gated."""

import json
import hashlib
import hmac
import os
import time as clock_time
import uuid
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
import httpx
from urllib.parse import urlencode

from lora_v2.api import create_app
from lora_v2.config import Settings
from lora_v2.daily_agent import (
    brief_due_at, create_brief, generate_due_briefs, planning_date, resolve_agent_followup,
)
from lora_v2.db import create_pool, migrate
from lora_v2.notifications import send_pending_telegram
from lora_v2.proactive import decide_proposal
from lora_v2.proposal_dialogue import resolve_proposal_reply


def _init_data(token: str, owner: int) -> str:
    values = {"auth_date": str(int(clock_time.time())),
              "user": json.dumps({"id": owner}, separators=(",", ":"))}
    check = "\n".join(f"{key}={value}" for key, value in sorted(values.items()))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    values["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(values)


def test_planning_phrases_and_routine_times() -> None:
    zone = ZoneInfo("Europe/Bucharest")
    now = datetime(2026, 10, 21, 10, tzinfo=zone)
    assert planning_date("Organizează-mi ziua de mâine", now) == date(2026, 10, 22)
    assert planning_date("Planifică ziua de azi", now) == date(2026, 10, 21)
    assert planning_date("Pune-mi un reminder mâine", now) is None
    routine = {"wake_time": "07:15:00", "morning_time": "09:00", "eod_time": "21:30"}
    assert brief_due_at("morning", now.date(), routine, "Europe/Bucharest").time() == time(9)
    assert brief_due_at("evening", now.date(), routine, "Europe/Bucharest").time() == time(21, 30)
    assert brief_due_at("morning", now.date(), {}, "Europe/Bucharest").time() == time(8)
    assert brief_due_at("morning", now.date(), {"wake_time": "07:15:00"}, "Europe/Bucharest").time() == time(7, 45)


@pytest.mark.asyncio
async def test_agent_plan_reads_data_and_waits_for_each_approval(monkeypatch: pytest.MonkeyPatch) -> None:
    url = os.getenv("LORA_V2_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Requires an isolated Lora v2 test database")
    from lora_v2 import daily_agent

    async def tools(*_args: object) -> tuple[list[str], bool]:
        return ["agenda", "tasks", "routine"], False

    async def priorities(_settings: Settings, _context: dict, candidates: list[tuple]) -> tuple[list[str], bool]:
        return [candidate[0] for candidate in candidates[:3]], False

    monkeypatch.setattr(daily_agent, "_choose_tools", tools)
    monkeypatch.setattr(daily_agent, "_choose_priorities", priorities)
    owner = uuid.uuid4().int % 1000000000
    settings = Settings(database_url=url, telegram_bot_token="test", telegram_user_id=owner)
    pool = await create_pool(settings)
    zone = ZoneInfo(settings.timezone)
    now = datetime(2026, 10, 22, 8, 5, tzinfo=zone)
    lesson_id, reminder_id, task_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    try:
        await migrate(pool)
        await pool.execute(
            """INSERT INTO calendar_entries(id,owner_id,kind,title,starts_at,ends_at)
            VALUES ($1,$2,'academic','Seminar', $3,$4),
            ($5,$2,'reminder','Sună administratorul',$6,NULL)""",
            lesson_id, owner, datetime(2026, 10, 22, 12, tzinfo=zone),
            datetime(2026, 10, 22, 14, tzinfo=zone), reminder_id,
            datetime(2026, 10, 22, 13, tzinfo=zone),
        )
        await pool.execute(
            "INSERT INTO tasks(id,owner_id,title,due_at) VALUES ($1,$2,'Trimite proiectul',$3)",
            task_id, owner, now - timedelta(days=1),
        )
        first = await create_brief(pool, settings, owner, now.date(), "morning",
                                   "scheduled:morning:2026-10-22", now=now)
        assert first["status"] == "ready"
        assert "Seminar" in first["summary"]
        assert {event["tool"] for event in first["tool_events"]} == {
            "selection", "agenda", "tasks", "routine",
        }
        proposals = await pool.fetch(
            "SELECT id,command FROM proposals WHERE owner_id=$1 AND source LIKE 'agent:%'",
            owner,
        )
        assert len(proposals) == 2
        assert await pool.fetchval("SELECT starts_at FROM calendar_entries WHERE id=$1", reminder_id) == datetime(
            2026, 10, 22, 13, tzinfo=zone,
        )
        assert await pool.fetchval("SELECT due_at FROM tasks WHERE id=$1", task_id) == now - timedelta(days=1)
        again = await create_brief(pool, settings, owner, now.date(), "morning",
                                   "scheduled:morning:2026-10-22", now=now)
        assert again["id"] == first["id"]
        assert await pool.fetchval(
            "SELECT count(*) FROM notification_outbox WHERE owner_id=$1 AND kind='agent_brief'",
            owner,
        ) == 1
        assert await generate_due_briefs(pool, settings, owner, now=now) == 0
        reminder_proposal = next(row for row in proposals if 'reschedule_entry' in row["command"])
        result = await decide_proposal(pool, settings, owner, reminder_proposal["id"], True)
        assert result is not None and result.status == "saved"
        assert await pool.fetchval("SELECT starts_at FROM calendar_entries WHERE id=$1", reminder_id) == datetime(
            2026, 10, 22, 14, 15, tzinfo=zone,
        )
        assert await pool.fetchval("SELECT due_at FROM tasks WHERE id=$1", task_id) == now - timedelta(days=1)
    finally:
        await pool.close()


@pytest.mark.asyncio
async def test_min_app_brief_is_owner_scoped(monkeypatch: pytest.MonkeyPatch) -> None:
    url = os.getenv("LORA_V2_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Requires an isolated Lora v2 test database")
    from lora_v2 import daily_agent

    async def tools(*_args: object) -> tuple[list[str], bool]:
        return ["agenda", "tasks", "routine"], False

    monkeypatch.setattr(daily_agent, "_choose_tools", tools)
    owner = uuid.uuid4().int % 1000000000
    settings = Settings(database_url=url, telegram_bot_token="test-token", telegram_user_id=owner)
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            day = datetime.now(ZoneInfo(settings.timezone)).date().isoformat()
            denied = await client.get("/api/v2/agent/briefs")
            assert denied.status_code == 401
            headers = {"X-Telegram-Init-Data": _init_data(settings.telegram_bot_token, owner)}
            created = await client.post("/api/v2/agent/briefs", headers=headers,
                                        json={"target_date": day})
            assert created.status_code == 200
            assert created.json()["status"] == "ready"
            listed = await client.get("/api/v2/agent/briefs", headers=headers)
            assert listed.status_code == 200
            assert listed.json()[0]["id"] == created.json()["id"]
            assert isinstance(listed.json()[0]["context"], dict)


@pytest.mark.asyncio
async def test_evening_brief_includes_unfinished_today_and_is_not_duplicated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    url = os.getenv("LORA_V2_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Requires an isolated Lora v2 test database")
    from lora_v2 import daily_agent

    async def tools(*_args: object) -> tuple[list[str], bool]:
        return ["agenda", "tasks", "routine"], True

    monkeypatch.setattr(daily_agent, "_choose_tools", tools)
    owner = uuid.uuid4().int % 1000000000
    settings = Settings(database_url=url, telegram_bot_token="test", telegram_user_id=owner)
    pool = await create_pool(settings)
    zone = ZoneInfo(settings.timezone)
    now = datetime(2026, 10, 22, 20, 5, tzinfo=zone)
    try:
        await migrate(pool)
        await pool.execute(
            """INSERT INTO calendar_entries(id,owner_id,kind,title,starts_at)
            VALUES ($1,$2,'reminder','Ia actele',$3)""",
            uuid.uuid4(), owner, now - timedelta(hours=2),
        )
        assert await generate_due_briefs(pool, settings, owner, now=now) == 1
        assert await generate_due_briefs(pool, settings, owner, now=now) == 0
        brief = await pool.fetchrow(
            "SELECT summary,target_date FROM agent_briefs WHERE owner_id=$1 AND mode='evening'",
            owner,
        )
        assert brief["target_date"] == now.date() + timedelta(days=1)
        assert "Ia actele" in brief["summary"]
        assert await pool.fetchval(
            "SELECT count(*) FROM notification_outbox WHERE owner_id=$1 AND kind='agent_brief'",
            owner,
        ) == 1
        sent: list[str] = []

        class FakeBot:
            async def send_message(self, chat_id: int, text: str) -> None:
                assert chat_id == owner
                sent.append(text)

        assert await send_pending_telegram(pool, FakeBot(), owner, now=now) == 1
        assert len(sent) == 1 and "Ia actele" in sent[0]
    finally:
        await pool.close()


@pytest.mark.asyncio
async def test_followup_revises_only_the_focused_proposal(monkeypatch: pytest.MonkeyPatch) -> None:
    url = os.getenv("LORA_V2_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Requires an isolated Lora v2 test database")
    from lora_v2 import daily_agent

    async def tools(*_args: object) -> tuple[list[str], bool]:
        return ["agenda", "tasks", "routine"], False

    async def priorities(_settings: Settings, _context: dict, candidates: list[tuple]) -> tuple[list[str], bool]:
        return [candidate[0] for candidate in candidates[:3]], False

    monkeypatch.setattr(daily_agent, "_choose_tools", tools)
    monkeypatch.setattr(daily_agent, "_choose_priorities", priorities)
    owner = uuid.uuid4().int % 1000000000
    settings = Settings(database_url=url, telegram_bot_token="test", telegram_user_id=owner)
    pool = await create_pool(settings)
    zone = ZoneInfo(settings.timezone)
    tomorrow = datetime.now(zone).date() + timedelta(days=1)
    class_start = datetime.combine(tomorrow, time(10), zone)
    reminder_id = uuid.uuid4()
    try:
        await migrate(pool)
        await pool.execute(
            """INSERT INTO calendar_entries(id,owner_id,kind,title,starts_at,ends_at)
            VALUES ($1,$2,'academic','Curs', $3,$4),
            ($5,$2,'reminder','Sună administratorul',$6,NULL)""",
            uuid.uuid4(), owner, class_start, class_start + timedelta(hours=2),
            reminder_id, class_start + timedelta(minutes=30),
        )
        plan = await create_brief(pool, settings, owner, tomorrow, "on_demand",
                                  f"test:{uuid.uuid4()}", now=datetime.now(zone))
        assert len(plan["context"]["proposal_ids"]) == 1
        answer = await resolve_agent_followup(pool, settings, owner, "Mai bine după ultimul curs")
        assert answer is not None and answer.status == "needs_input"
        proposal = await pool.fetchrow(
            "SELECT command,version FROM proposals WHERE id=$1",
            uuid.UUID(plan["context"]["proposal_ids"][0]),
        )
        assert proposal["version"] == 2
        updated_at = datetime.fromisoformat(json.loads(proposal["command"])["data"]["starts_at"])
        assert updated_at.astimezone(zone) == class_start + timedelta(hours=2, minutes=15)
        assert await pool.fetchval("SELECT starts_at FROM calendar_entries WHERE id=$1", reminder_id) == (
            class_start + timedelta(minutes=30)
        )
        accepted = await resolve_proposal_reply(pool, settings, owner, "da", datetime.now(zone))
        assert accepted is not None and accepted.status == "saved"
        assert await pool.fetchval("SELECT starts_at FROM calendar_entries WHERE id=$1", reminder_id) == (
            class_start + timedelta(hours=2, minutes=15)
        )
    finally:
        await pool.close()
