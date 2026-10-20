"""Receipt photo must reconcile its total and wait for one atomic approval."""

import json
import os
import uuid
import hashlib
import hmac
import time
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
import httpx
from urllib.parse import urlencode

from lora_v2.agent import Candidate, Interpretation
from lora_v2.config import Settings
from lora_v2.api import create_app
from lora_v2.db import create_pool, migrate
from lora_v2.models import Command
from lora_v2.processor import process_capture
from lora_v2.proactive import decide_proposal
from lora_v2.receipts import interpret_receipt_photo, looks_like_receipt
from lora_v2.service import capture


def test_receipt_detection_requires_receipt_evidence() -> None:
    assert looks_like_receipt("BON FISCAL\nCIF RO12345\nTOTAL 35,00 LEI")
    assert not looks_like_receipt("Piept de pui cu piure pe farfurie")


@pytest.mark.asyncio
async def test_receipt_total_mismatch_never_creates_a_proposal(monkeypatch: pytest.MonkeyPatch) -> None:
    async def ocr(_settings: Settings, _reference: str, *, try_apple: bool = False) -> str:
        return "BON FISCAL\nCIF RO12345\nPÂINE 10,00\nTOTAL 15,00 LEI"

    class FakeClient:
        def __init__(self, host: str) -> None:
            self.host = host

        async def chat(self, **_kwargs: object) -> dict[str, dict[str, str]]:
            return {"message": {"content": json.dumps({
                "merchant": "Magazin", "total_amount": "15.00",
                "items": [{"name": "Pâine", "amount": "10.00", "category": "mâncare"}],
            })}}

    monkeypatch.setattr("lora_v2.receipts.extract_ocr", ocr)
    monkeypatch.setattr("lora_v2.receipts.AsyncClient", FakeClient)
    settings = Settings(database_url="test", telegram_bot_token="test", telegram_user_id=123)
    result = await interpret_receipt_photo(settings, "photo.jpg", "bon", datetime.now(ZoneInfo(settings.timezone)))
    assert result is not None and result.actions == []
    assert "Nu salvez" in (result.reply or "")


@pytest.mark.asyncio
async def test_receipt_products_are_saved_atomically_only_after_approval(monkeypatch: pytest.MonkeyPatch) -> None:
    url = os.getenv("LORA_V2_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set LORA_V2_TEST_DATABASE_URL to an isolated test database")
    settings = Settings(database_url=url, telegram_bot_token="test", telegram_user_id=123)
    owner = uuid.uuid4().int % 1000000000
    pool = await create_pool(settings)

    async def receipt(_settings: Settings, reference: str, _caption: str, now: datetime) -> Interpretation:
        return Interpretation(actions=[Candidate(
            type="log_receipt", merchant="Profi", spent_at=now.isoformat(),
            total_amount=17, receipt_ref=reference, confidence=0.8,
            receipt_items=[
                {"name": "Paine alba", "amount": "5.00", "category": "altele"},
                {"name": "Baterii", "amount": "12.00", "category": "utilități"},
            ],
        )])

    try:
        await migrate(pool)
        await pool.execute(
            """INSERT INTO receipt_product_rules(owner_id,pattern,merchant_key,clean_name,category)
            VALUES ($1,'paine alba','profi','Pâine albă','mâncare')""", owner,
        )
        monkeypatch.setattr("lora_v2.processor.interpret_receipt_photo", receipt)
        captured = await capture(pool, owner, "test", str(uuid.uuid4()), "bon",
                                 content_type="photo", attachment_ref="private-photo.jpg")
        result = await process_capture(pool, settings, owner, captured["id"])
        assert result[0].status == "needs_input"
        assert "Pâine albă" in result[0].message
        assert "mâncare" in result[0].message
        assert await pool.fetchval("SELECT count(*) FROM expenses WHERE owner_id=$1", owner) == 0
        proposal_id = uuid.UUID(result[0].details["proposal_id"])
        approved = await decide_proposal(pool, settings, owner, proposal_id, True)
        assert approved is not None and approved.status == "saved"
        rows = await pool.fetch(
            """SELECT amount,category,description,receipt_ref FROM expenses
            WHERE owner_id=$1 ORDER BY amount""", owner,
        )
        assert len(rows) == 2
        assert sum((row["amount"] for row in rows), Decimal("0")) == Decimal("17.00")
        assert [(row["category"], row["description"]) for row in rows] == [
            ("mâncare", "Pâine albă"), ("utilități", "Baterii")]
        assert all(row["receipt_ref"] == "private-photo.jpg" for row in rows)
        assert await decide_proposal(pool, settings, owner, proposal_id, True) is None
        assert await pool.fetchval("SELECT count(*) FROM expenses WHERE owner_id=$1", owner) == 2
    finally:
        await pool.close()


def test_receipt_command_rejects_partial_total() -> None:
    with pytest.raises(ValueError):
        Command(type="log_receipt", data={
            "merchant": "Profi", "total_amount": "20.00", "currency": "RON",
            "spent_at": "2026-10-20T12:00:00+03:00", "receipt_ref": "photo.jpg",
            "items": [{"name": "Pâine", "amount": "5.00", "category": "mâncare"}],
        }).payload()


@pytest.mark.asyncio
async def test_uncertain_product_requires_inline_review_before_approval(monkeypatch: pytest.MonkeyPatch) -> None:
    url = os.getenv("LORA_V2_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set LORA_V2_TEST_DATABASE_URL to an isolated test database")
    owner = uuid.uuid4().int % 1000000000
    settings = Settings(database_url=url, telegram_bot_token="test", telegram_user_id=owner)
    app = create_app(settings)

    async def receipt(_settings: Settings, reference: str, _caption: str, now: datetime) -> Interpretation:
        return Interpretation(actions=[Candidate(
            type="log_receipt", merchant="Magazin", spent_at=now.isoformat(),
            total_amount=7, receipt_ref=reference, confidence=0.8,
            receipt_items=[{"name": "Produs necunoscut", "amount": "7.00", "category": None}],
        )])

    monkeypatch.setattr("lora_v2.processor.interpret_receipt_photo", receipt)
    values = {"auth_date": str(int(time.time())), "user": json.dumps({"id": owner}, separators=(",", ":"))}
    check = "\n".join(f"{key}={value}" for key, value in sorted(values.items()))
    secret = hmac.new(b"WebAppData", b"test", hashlib.sha256).digest()
    values["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    headers = {"X-Telegram-Init-Data": urlencode(values)}

    async with app.router.lifespan_context(app):
        item = await capture(app.state.pool, owner, "test", str(uuid.uuid4()), "bon",
                             content_type="photo", attachment_ref="private-photo.jpg")
        result = await process_capture(app.state.pool, settings, owner, item["id"])
        proposal_id = result[0].details["proposal_id"]
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            blocked = await client.post(f"/api/v2/proposals/{proposal_id}/decision",
                                        headers=headers, json={"accept": True})
            assert blocked.status_code == 200 and blocked.json()["status"] == "needs_input"
            assert await app.state.pool.fetchval("SELECT count(*) FROM expenses WHERE owner_id=$1", owner) == 0
            edited = await client.put(f"/api/v2/proposals/{proposal_id}/receipt", headers=headers,
                                      json={"expected_version": 1, "merchant": "Magazin",
                                            "total_amount": "7.00", "items": [{"name": "Produs necunoscut",
                                            "amount": "7.00", "category": "casă"}]})
            assert edited.status_code == 200 and edited.json()["version"] == 2
            stale = await client.put(f"/api/v2/proposals/{proposal_id}/receipt", headers=headers,
                                     json={"expected_version": 1, "merchant": "Magazin",
                                           "total_amount": "7.00", "items": [{"name": "Produs necunoscut",
                                           "amount": "7.00", "category": "casă"}]})
            assert stale.status_code == 409
            approved = await client.post(f"/api/v2/proposals/{proposal_id}/decision",
                                         headers=headers, json={"accept": True})
            assert approved.status_code == 200 and approved.json()["status"] == "saved"
            assert await app.state.pool.fetchval(
                "SELECT category FROM expenses WHERE owner_id=$1", owner) == "casă"
