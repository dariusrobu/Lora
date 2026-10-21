"""University notes are private, editable and guarded against stale updates."""

import hashlib
import hmac
import json
import os
import time
import uuid
from urllib.parse import urlencode

import httpx
import pytest

from lora_v2.api import create_app
from lora_v2.config import Settings


def _auth(token: str, owner: int) -> str:
    values = {"auth_date": str(int(time.time())),
              "user": json.dumps({"id": owner}, separators=(",", ":"))}
    check = "\n".join(f"{key}={value}" for key, value in sorted(values.items()))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    values["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(values)


@pytest.mark.asyncio
async def test_university_note_crud_is_owner_scoped_and_versioned() -> None:
    url = os.getenv("LORA_V2_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Requires isolated Lora v2 test database")
    owner = uuid.uuid4().int % 1000000000
    other = uuid.uuid4().int % 1000000000
    settings = Settings(database_url=url, telegram_bot_token="test-token", telegram_user_id=owner)
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        headers = {"X-Telegram-Init-Data": _auth(settings.telegram_bot_token, owner)}
        other_headers = {"X-Telegram-Init-Data": _auth(settings.telegram_bot_token, other)}
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            created = await client.post("/api/v2/university/notes", headers=headers,
                                        json={"title": "Seminar", "body": "Idei de reținut"})
            assert created.status_code == 201
            note_id = created.json()["id"]
            notes = await client.get("/api/v2/university/notes", headers=headers)
            assert notes.status_code == 200 and notes.json()[0]["body"] == "Idei de reținut"
            assert (await client.get("/api/v2/university/notes", headers=other_headers)).status_code == 403
            changed = await client.put(f"/api/v2/university/notes/{note_id}", headers=headers,
                                       json={"title": "Seminar 2", "body": "Text nou", "expected_version": 1})
            assert changed.status_code == 200 and changed.json()["version"] == 2
            stale = await client.put(f"/api/v2/university/notes/{note_id}", headers=headers,
                                     json={"title": "Greșit", "expected_version": 1})
            assert stale.status_code == 409
            forbidden = await client.delete(f"/api/v2/university/notes/{note_id}?expected_version=2",
                                            headers=other_headers)
            assert forbidden.status_code == 403
            deleted = await client.delete(f"/api/v2/university/notes/{note_id}?expected_version=2",
                                          headers=headers)
            assert deleted.status_code == 200
            assert (await client.get("/api/v2/university/notes", headers=headers)).json() == []
