"""Shared Telegram message capture for the v2 bot and the legacy polling bridge."""

import asyncpg
from telegram import Update

from lora_v2.config import Settings
from lora_v2.media import save_photo, save_voice
from lora_v2.queries import answer_read_intent, read_intent
from lora_v2.service import capture


async def handle_owner_message(
    update: Update, pool: asyncpg.Pool, settings: Settings,
) -> bool:
    if (not update.effective_user or update.effective_user.id != settings.telegram_user_id
            or not update.message or not update.effective_chat
            or update.effective_chat.type != "private"):
        return False
    message = update.message
    content_type = "text"
    attachment_ref = None
    message_text = message.text or message.caption or ""
    if message.text:
        intent = read_intent(message.text)
        if intent:
            await message.reply_text(await answer_read_intent(
                pool, settings, settings.telegram_user_id, intent,
            ))
            return True
    try:
        if message.photo:
            photo = message.photo[-1]
            file = await photo.get_file()
            attachment_ref = save_photo(settings, bytes(await file.download_as_bytearray()))
            content_type = "photo"
        elif message.voice:
            file = await message.voice.get_file()
            attachment_ref = save_voice(settings, bytes(await file.download_as_bytearray()))
            content_type = "voice"
        elif not message_text:
            return False
    except (ValueError, OSError):
        await message.reply_text("Nu pot citi fișierul. Trimite o fotografie sau un mesaj vocal mai mic.")
        return True
    row = await capture(
        pool, settings.telegram_user_id, "telegram", str(update.update_id),
        message_text, content_type=content_type, attachment_ref=attachment_ref,
    )
    await message.reply_text(
        "Am păstrat mesajul. Îl procesez acum…" if row["status"] == "captured"
        else "Mesajul acesta este deja înregistrat."
    )
    return True
