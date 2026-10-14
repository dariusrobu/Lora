"""Invisible Telegram Mini App authentication; no password or login screen."""

import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl

from fastapi import Header, HTTPException

from lora_v2.config import Settings


def verify_init_data(init_data: str, settings: Settings, now: int | None = None) -> int:
    values = dict(parse_qsl(init_data, keep_blank_values=True))
    received = values.pop("hash", "")
    if not received:
        raise HTTPException(status_code=401, detail="Telegram verification missing")
    check = "\n".join(f"{key}={value}" for key, value in sorted(values.items()))
    secret = hmac.new(b"WebAppData", settings.telegram_bot_token.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received):
        raise HTTPException(status_code=401, detail="Telegram verification failed")
    try:
        auth_date = int(values["auth_date"])
        user_id = int(json.loads(values["user"])["id"])
    except (KeyError, ValueError, TypeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=401, detail="Invalid Telegram identity") from exc
    current = now if now is not None else int(time.time())
    if auth_date > current + 60 or current - auth_date > 86400:
        raise HTTPException(status_code=401, detail="Telegram session expired")
    if user_id != settings.telegram_user_id:
        raise HTTPException(status_code=403, detail="Unauthorized Telegram user")
    return user_id


def owner_from_header(settings: Settings):
    async def dependency(x_telegram_init_data: str = Header(default="")) -> int:
        if not x_telegram_init_data:
            raise HTTPException(status_code=401, detail="Open Lora from Telegram")
        return verify_init_data(x_telegram_init_data, settings)

    return dependency
