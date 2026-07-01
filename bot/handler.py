from bot.callback_utils import make_callback_data
import traceback
import json
import logging
from datetime import date
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery, Message
import os
from telegram.ext import ContextTypes
from core.config import TELEGRAM_USER_ID
from db.queries.profile import get_user_profile
from bot.formatter import escape_md, safe_markdown, split_message

# Global monkey-patching of CallbackQuery and Message class methods to safely edit messages with MarkdownV2 format without crashing on unescaped symbols.
_orig_callback_edit = CallbackQuery.edit_message_text
async def _safe_callback_edit(self, *args, **kwargs):
    if kwargs.get("parse_mode") == "MarkdownV2":
        if len(args) > 0 and isinstance(args[0], str):
            args = list(args)
            args[0] = safe_markdown(args[0])
        elif "text" in kwargs and isinstance(kwargs["text"], str):
            kwargs["text"] = safe_markdown(kwargs["text"])
    return await _orig_callback_edit(self, *args, **kwargs)
CallbackQuery.edit_message_text = _safe_callback_edit

_orig_message_edit = Message.edit_text
async def _safe_message_edit(self, *args, **kwargs):
    if kwargs.get("parse_mode") == "MarkdownV2":
        if len(args) > 0 and isinstance(args[0], str):
            args = list(args)
            args[0] = safe_markdown(args[0])
        elif "text" in kwargs and isinstance(kwargs["text"], str):
            kwargs["text"] = safe_markdown(kwargs["text"])
    return await _orig_message_edit(self, *args, **kwargs)
Message.edit_text = _safe_message_edit

from core.context import build_context
from core.gemini import get_gemini_response
from core.router import route_intent
from db.queries.history import save_message, get_recent_history
from core.stats import update_last_message


async def security_check(update: Update) -> bool:
    """Rejects non-whitelisted user IDs silently."""
    if not update.effective_user:
        return False

    is_authorized = update.effective_user.id == TELEGRAM_USER_ID
    if not is_authorized:
        print(
            f"❌ UNAUTHORIZED: Access attempt by ID {update.effective_user.id} (Expected {TELEGRAM_USER_ID})"
        )
    else:
        print(f"✅ AUTHORIZED: User ID {update.effective_user.id}")
    return is_authorized


async def voice_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, pool):
    """Handles incoming voice messages, transcribes them, and follows the text flow."""
    if not await security_check(update):
        return

    try:
        from bot.voice import transcribe_voice
        from core.gemini import normalize_voice_text

        try:
            text, voice_uri = await transcribe_voice(update, context)
            if not text:
                raise ValueError("Buit-in check failed")
        except ValueError as e:
            # Romanian error responses as requested
            await update.message.reply_text(str(e))
            return
        except Exception as e:
            print(f"Transcription error: {e}")
            await update.message.reply_text(
                "Nu am putut înțelege mesajul vocal — încearcă din nou 🎙"
            )
            return

        # Normalize raw STT text before intent analysis
        print(f"🎙 VOICE TRANSCRIBED (raw): {repr(text)}", flush=True)
        # normalize_voice_text is still useful for cleaning up, but we also have the URI now
        text = await normalize_voice_text(text)

        return await message_handler(
            update, context, pool, text=text, source="voice", voice_uri=voice_uri
        )

    except Exception as e:
        print(f"ERROR in voice_handler: {e}")
        traceback.print_exc()


async def focus_command(update, context):
    pool = context.bot_data.get("pool")
    text = update.message.text

    parts = text.split()
    duration = 25
    if len(parts) > 1 and parts[1].isdigit():
        duration = int(parts[1])

    from modules.focus import handle_focus_intent

    reply, markup = await handle_focus_intent(
        pool, "focus_start", {"duration_min": duration}, bot=context.bot
    )
    await update.message.reply_text(reply, parse_mode="MarkdownV2")


async def stopfocus_command(update, context):
    pool = context.bot_data.get("pool")
    from modules.focus import handle_focus_intent

    reply, markup = await handle_focus_intent(pool, "focus_stop", {}, bot=context.bot)
    await update.message.reply_text(reply, parse_mode="MarkdownV2")


async def timeblock_command(update, context):
    pool = context.bot_data.get("pool")
    await update.message.reply_text("🗓 Generez time block-ul tău... un moment!")
    from modules.planner import generate_time_block

    reply, markup = await generate_time_block(pool)
    await update.message.reply_text(reply, parse_mode="MarkdownV2")


async def uni_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles /uni command — opens academic dashboard."""
    pool = context.bot_data.get("pool")
    if not pool:
        await update.message.reply_text("Database pool error.")
        return
    await show_uni_dashboard(update.message, pool, send_new=True)


async def workout_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles /workout command — opens workout dashboard."""
    pool = context.bot_data.get("pool")
    if not pool:
        await update.message.reply_text("Database pool error.")
        return
    from modules.workout import get_workout_dashboard

    text, markup = await get_workout_dashboard(pool)
    await update.message.reply_text(text, parse_mode="MarkdownV2", reply_markup=markup)


async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, pool):
    """Handles incoming photos, sending them to the Vision Module."""
    if not await security_check(update):
        return

    try:
        from core.vision import analyze_image, process_vision_result
        from core.gemini import client

        # Send loading message
        loading_msg = await update.message.reply_text("Analizând imaginea... 👁️")

        # Get highest resolution photo
        photo_file = await update.message.photo[-1].get_file()
        photo_bytes = await photo_file.download_to_memory()

        caption = update.message.caption

        # Analyze using Vision Module
        result = await analyze_image(client, bytes(photo_bytes), caption)

        if result.get("type") == "error":
            await loading_msg.edit_text(
                result.get("reply", "Eroare la procesarea imaginii.")
            )
            return

        profile = await get_user_profile(pool, TELEGRAM_USER_ID)

        # Process result and get formatting
        reply_text, keyboard = await process_vision_result(
            pool, result, profile, client
        )

        # Edit loading message with real reply
        try:
            await loading_msg.edit_text(
                reply_text, parse_mode="MarkdownV2", reply_markup=keyboard
            )
        except Exception as edit_err:
            print(f"Error editing loading msg with MarkdownV2: {edit_err}")
            await loading_msg.edit_text(reply_text, reply_markup=keyboard)

    except Exception as e:
        pass

        print(f"Error handling photo: {e}")
        traceback.print_exc()
        try:
            await update.message.reply_text("A apărut o eroare la procesarea pozei.")
        except Exception:
            pass


async def location_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, pool):
    """Handles incoming location messages to sync user's current position."""
    if not await security_check(update):
        return

    try:
        from db.queries.profile import update_user_profile
        from core.config import OPENWEATHER_API_KEY
        import httpx

        if not update.message or not update.message.location:
            return

        location = update.message.location
        lat, lon = location.latitude, location.longitude

        # 1. Reverse Geocoding (get city name)
        city_name = "Locație necunoscută"
        if OPENWEATHER_API_KEY:
            try:
                url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={OPENWEATHER_API_KEY}&units=metric&lang=ro"
                async with httpx.AsyncClient() as client:
                    res = await client.get(url, timeout=5.0)
                    if res.status_code == 200:
                        city_name = res.json().get("name", city_name)
            except Exception as e:
                print(f"Reverse geocoding error: {e}")

        # 2. Persist coordinates and city
        await update_user_profile(
            pool,
            update.effective_user.id,
            latitude=lat,
            longitude=lon,
            city_name=city_name,
        )

        # 3. Process Geofencing & Intelligent Notifications
        from core.geofencing import process_geofencing

        await process_geofencing(
            pool, update.effective_user.id, lat, lon, context.application
        )

        print(f"📍 LOCATION SYNCED: {lat}, {lon} ({city_name})")

        # Only reply if it's a NEW message (not a Live Location update)
        if not update.edited_message:
            msg = f"📍 *Locație sincronizată\\!*\\n\nAcum suntem în *{city_name}*\\. Îți voi oferi date meteo și sugestii exacte pentru zona ta\\. 🌐"
            await update.message.reply_text(msg, parse_mode="MarkdownV2")

    except Exception as e:
        print(f"ERROR in location_handler: {e}")
        traceback.print_exc()
        await update.message.reply_text("Nu am putut procesa locația.")


async def set_home_command(update: Update, context: ContextTypes.DEFAULT_TYPE, pool):
    """Sets current location as HOME."""
    if not await security_check(update):
        return

    profile = await get_user_profile(pool, TELEGRAM_USER_ID)
    lat = profile.get("latitude")
    lon = profile.get("longitude")

    if not lat or not lon:
        await update.message.reply_text(
            "❌ Nu am locația ta curentă. Te rog trimite-mi locația mai întâi!"
        )
        return

    from db.queries.profile import update_user_profile

    await update_user_profile(
        pool, TELEGRAM_USER_ID, home_latitude=lat, home_longitude=lon, is_at_home=True
    )

    msg = "🏠 *Locație setată ca ACASĂ\\!*\\n\nDe acum voi ști când pleci și când revii pentru a-ți oferi asistență inteligentă\\. 🦾"
    await update.message.reply_text(msg, parse_mode="MarkdownV2")


async def save_location_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE, pool
):
    """Saves current location with a name."""
    if not await security_check(update):
        return

    name = " ".join(context.args).strip()
    if not name:
        await update.message.reply_text(
            "❌ Te rog specifică un nume pentru locație. Ex: `/save sala`",
            parse_mode="MarkdownV2",
        )
        return

    profile = await get_user_profile(pool, TELEGRAM_USER_ID)
    lat = profile.get("latitude")
    lon = profile.get("longitude")

    if not lat or not lon:
        await update.message.reply_text(
            "❌ Nu am locația ta curentă. Trimite-mi locația mai întâi!"
        )
        return

    from db.queries.locations import add_saved_location

    await add_saved_location(pool, TELEGRAM_USER_ID, name, float(lat), float(lon))

    msg = f"📍 *Locație salvată:* `{name}`\\!\n\nDe acum Lora va recunoaște acest loc și te va ajuta în funcție de context\\. 🌐"
    await update.message.reply_text(msg, parse_mode="MarkdownV2")


async def list_locations_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE, pool
):
    """Lists all saved locations."""
    if not await security_check(update):
        return

    from db.queries.locations import list_saved_locations

    locs = await list_saved_locations(pool, TELEGRAM_USER_ID)

    if not locs:
        await update.message.reply_text(
            "Nu ai nicio locație salvată încă\\. Folosește `/save nume` pentru a adăuga una\\.",
            parse_mode="MarkdownV2",
        )
        return

    lines = ["📍 *Locațiile tale salvate:*\n"]
    for loc in locs:
        lines.append(
            f"• *{loc['name']}* — `{loc['latitude']:.4f}, {loc['longitude']:.4f}`"
        )

    await update.message.reply_text("\n".join(lines), parse_mode="MarkdownV2")


async def location_status_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE, pool
):
    """Shows current location status and geofencing info."""
    if not await security_check(update):
        return

    profile = await get_user_profile(pool, TELEGRAM_USER_ID)
    lat = profile.get("latitude")
    lon = profile.get("longitude")
    city = profile.get("city_name", "Necunoscut")
    is_home = profile.get("is_at_home")

    home_lat = profile.get("home_latitude")
    home_lon = profile.get("home_longitude")
    curr_spot = profile.get("current_location_name")

    status = "🏠 Acasă" if is_home else "🚀 Plecat"
    home_info = f"Setată la `{home_lat}, {home_lon}`" if home_lat else "Nesetată"
    spot_info = (
        f"📍 Suntem la: *{curr_spot}*"
        if curr_spot
        else "📍 Nu suntem într-o locație salvată"
    )

    msg = (
        f"📍 *Status Locație*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🌐 *Oraș:* {city}\n"
        f"📍 *Coordonate:* `{lat}, {lon}`\n"
        f"🏠 *Stare:* {status}\n"
        f"🏠 *Locație salvată:* {spot_info}\n"
        f"📍 *Baza (Acasă):* {home_info}\n\n"
        f"Folosește `/save nume` pentru a adăuga locul curent în memorie\\."
    )
    await update.message.reply_text(msg, parse_mode="MarkdownV2")


async def message_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    pool,
    text=None,
    source: str = "text",
    voice_uri: str | None = None,
):
    try:
        update_last_message()
        user_id = update.effective_user.id if update.effective_user else "Unknown"
        print(
            f"📥 INCOMING: Update ID {update.update_id} from user_id {user_id}",
            flush=True,
        )

        # Use provided text or fallback to message text
        if text is None and update.message:
            text = update.message.text

        # Pre-process text (minimal normalization, let Gemini do the heavy lifting)
        if text:
            text = text.strip()

        print(
            f"📥 RECEIVED: Update ID {update.update_id} from user_id {user_id} - Text: {repr(text)}"
        )

        if not await security_check(update):
            return

        # --- COMANDĂ CALENDAR (DETECTION) ---
        if text:
            clean_text = text.strip().lower()
            if clean_text.startswith("/test_calendar"):
                from core.icloud import test_connection

                res = await test_connection()
                status = "✅" if res["success"] else "❌"
                msg = f"{status} *iCloud Status*\n\n{escape_md(res['message'])}\n\n"
                if res.get("calendars"):
                    msg += "Calendare găsite:\n" + "\n".join(
                        f"• {escape_md(c)}" for c in res["calendars"]
                    )
                await update.message.reply_text(msg, parse_mode="MarkdownV2")
                return

            if clean_text.startswith("/sync_calendar"):
                from modules.calendar_module import handle_calendar_intent

                reply, _ = await handle_calendar_intent(pool, "calendar_sync", {})
                await update.message.reply_text(reply, parse_mode="MarkdownV2")
                return

            if clean_text.startswith("/briefing"):
                from scheduler.jobs import send_morning_briefing

                await update.message.reply_text(
                    "🔄 Pregătesc briefing-ul... un moment."
                )
                await send_morning_briefing(context.application, pool, force=True)
                return

        # ── GROUP ROUTING ──
        # If in a group, only respond if explicitly mentioned
        if update.effective_chat and update.effective_chat.type in (
            "group",
            "supergroup",
        ):
            # Lazy-get bot username
            bot_username = context.application.bot_data.get("bot_username")
            if not bot_username:
                me = await context.bot.get_me()
                bot_username = me.username
                context.application.bot_data["bot_username"] = bot_username

            # Check for mention in entities or text
            is_mentioned = False
            if update.message and update.message.entities:
                for ent in update.message.entities:
                    if ent.type == "mention":
                        mentioned_text = update.message.text[
                            ent.offset : ent.offset + ent.length
                        ].lower()
                        if f"@{bot_username.lower()}" == mentioned_text:
                            is_mentioned = True
                            break

            # Only exit early if in a group and not mentioned
            if (
                not is_mentioned
                and f"@{bot_username.lower()}" not in (text or "").lower()
            ):
                print(
                    f"🔇 LORA SILENT: Message in group {update.effective_chat.id} doesn't mention @{bot_username}"
                )
                return

        telegram_id = update.effective_user.id

        # Non-text message handling
        if not update.message or (not text and not update.message.voice):
            if update.message and (
                update.message.photo or update.message.video or update.message.sticker
            ):
                await update.message.reply_text(
                    "I can only read text for now — what would you like to do?"
                )
            return

        # Handle /tasks command
        if text.startswith("/tasks"):
            from modules.tasks import get_tasks_dashboard

            text_out, markup = await get_tasks_dashboard(pool)
            await update.message.reply_text(
                text_out, parse_mode="MarkdownV2", reply_markup=markup
            )
            return

        if text == "/memory":
            from modules.memory import handle_memory_intent

            text_out, markup, _ = await handle_memory_intent(pool, "memory_view", {})
            await update.message.reply_text(
                text_out, parse_mode="MarkdownV2", reply_markup=markup
            )
            return

        # Handle /reload command
        if text == "/reload":
            await update.message.reply_text(
                "🔄 Reloading Lora... I'll be back in a second!"
            )
            import os
            import sys
            from db.connection import close_pool

            await close_pool()
            os.execl(sys.executable, sys.executable, *sys.argv)
            return

        # Handle /podcast command
        if text == "/podcast":
            from scheduler.jobs import send_morning_briefing

            await update.message.reply_text(
                "🎙️ Generăm podcast-ul tău personal... un moment!"
            )

            try:
                await send_morning_briefing(context.application, pool, force=True)
            except Exception as e:
                print(f"Podcast manual trigger error: {e}", flush=True)
                await update.message.reply_text(
                    f"❌ Scuze, a apărut o eroare la generarea podcast-ului: {e}"
                )
            return

        # Handle /weeklyreview command
        if text == "/weeklyreview":
            from scheduler.jobs import send_weekly_review

            await update.message.reply_text(
                "📊 Generăm review-ul tău săptămânal... un moment!"
            )

            try:
                await send_weekly_review(context.application, pool)
            except Exception as e:
                print(f"Weekly review manual trigger error: {e}", flush=True)
                await update.message.reply_text(
                    f"❌ Eroare la generarea review-ului: {e}"
                )
            return

        # Handle /eod command
        if text == "/eod":
            from scheduler.jobs import send_eod_reflection

            try:
                await send_eod_reflection(context.application, pool, force=True)
            except Exception as e:
                print(f"EOD manual trigger error: {e}", flush=True)
                await update.message.reply_text(f"❌ Eroare la EOD: {e}")
            return

        # Handle /lastweek command
        if text == "/lastweek":
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT content, week_start, week_end FROM weekly_reviews ORDER BY created_at DESC LIMIT 1"
                )
                if not row:
                    await update.message.reply_text(
                        "Nu am găsit niciun raport săptămânal încă."
                    )
                    return

                header = f"📊 *Weekly Review: {row['week_start'].strftime('%d %b')} — {row['week_end'].strftime('%d %b')}*\\n\\n"
                pass
                final_text = header + safe_markdown(row["content"])

                chunks = split_message(final_text)
                for chunk in chunks:
                    await update.message.reply_text(chunk, parse_mode="MarkdownV2")
            return

        # Handle /monthlyreview command
        if text == "/monthlyreview":
            from scheduler.jobs import send_monthly_review
            from db.queries.profile import update_user_profile

            await update.message.reply_text(
                "📊 Generăm review-ul tău lunar... un moment!"
            )

            try:
                # Reset last_monthly_review_date to None to allow manual trigger
                await update_user_profile(
                    pool, TELEGRAM_USER_ID, last_monthly_review_date=None
                )
                await send_monthly_review(context.bot, pool)
            except Exception as e:
                print(f"Monthly review manual trigger error: {e}", flush=True)
                await update.message.reply_text(
                    f"❌ Eroare la generarea review-ului lunar: {e}"
                )
            return

        # Handle /habitstreaks command

        # Handle /journal and /eod commands
        if text == "/journal":
            from db.queries.profile import update_user_profile
            from core.config import TELEGRAM_USER_ID as TG_UID
            from scheduler.jobs import send_journal_night

            try:
                await update_user_profile(pool, TG_UID, last_journal_date=None)
                await send_journal_night(context.application, pool)
            except Exception as e:
                print(f"Journal night manual trigger error: {e}", flush=True)
                await update.message.reply_text(
                    f"❌ Eroare la inițierea journal-ului: {e}"
                )
            return

        if text == "/eod":
            from db.queries.profile import update_user_profile
            from core.config import TELEGRAM_USER_ID as TG_UID
            from scheduler.jobs import send_eod_reflection

            try:
                await update_user_profile(pool, TG_UID, last_eod_date=None)
                await send_eod_reflection(context.application, pool)
            except Exception as e:
                print(f"EOD reflection manual trigger error: {e}", flush=True)
                await update.message.reply_text(
                    f"❌ Eroare la inițierea EOD reflection: {e}"
                )
            return
        # Handle /plan command
        if text == "/plan":
            from db.queries.profile import update_user_profile
            from core.config import TELEGRAM_USER_ID as TG_UID
            from core.state import set_state
            from modules.planner import get_day_preview

            try:
                await update_user_profile(pool, TG_UID, last_plan_date=None)
                preview = await get_day_preview(pool)
                await update.message.reply_text(preview, parse_mode="MarkdownV2")
                await set_state(
                    pool, "awaiting_day_plan_input", "day_plans", "generate", None
                )
            except Exception as e:
                print(f"Plan manual trigger error: {e}", flush=True)
                await update.message.reply_text(f"❌ Eroare la inițierea planului: {e}")
            return

        # 3.8 Health Chart Direct Bypass (to avoid Gemini misinterpretation)
        health_chart_triggers = [
            "grafic health",
            "grafic somn",
            "grafic apă",
            "grafic apa",
            "grafic greutate",
            "cum am dormit",
        ]
        low_text = text.lower()
        if any(trigger in low_text for trigger in health_chart_triggers):
            intent_response = {
                "intent": "health_chart",
                "module": "health",
                "data": {"_original_reply": "Generăm graficul tău... 📊"},
                "reply": "Generăm graficul tău... 📊",
            }
            final_reply, reply_markup, _ = await route_intent(
                pool, intent_response, user_id=telegram_id, bot=context.bot
            )
            if final_reply:
                # Save assistant reply to history
                await save_message(pool, telegram_id, "assistant", final_reply)
                await update.message.reply_text(
                    final_reply, parse_mode="MarkdownV2", reply_markup=reply_markup
                )
            return

        # Handle /start command — triggers onboarding
        if text == "/start":
            from bot.onboarding import start_onboarding
            await start_onboarding(update, context, pool)
            return

        # Phase 3: Gemini Brain integration
        # 1. Get history (last 8 messages) BEFORE saving current message
        history = await get_recent_history(pool, telegram_id, limit=6)

        # 2. Save current user message to history
        await save_message(pool, telegram_id, "user", text)

        # Phase 8: State Check (Confirmations / Edits)
        from core.state import get_state, clear_state

        state = await get_state(pool)

        # Check for pending action in state (HITL Lock)
        from core.state import get_pending_action

        pending_act = await get_pending_action(pool)
        if pending_act:
            await update.message.reply_text(
                "Te rog să confirmi sau să anulezi acțiunea curentă mai întâi."
            )
            return

        # Skills State Handling
        if state and state.get("state_type") and state["state_type"].startswith("skills_"):
            from modules.skills import handle_skills_message

            if await handle_skills_message(update, context, pool, state):
                return

        # Reading State Handling
        if state and state.get("state_type") and state["state_type"].startswith("reading_"):
            from modules.reading import handle_reading_message

            if await handle_reading_message(update, pool, state):
                return

        if state and state.get("state_type"):
            print(
                f"🔄 STATE ACTIVE: {state['state_type']} for {state['module']}:{state['action']}",
                flush=True,
            )
            if state["state_type"] == "awaiting_confirmation":
                low_text = text.lower()
                if any(
                    word in low_text
                    for word in ["yes", "yeah", "do it", "confirm", "sure", "da"]
                ):
                    data = {"id": state["item_id"], "confirmed": True}
                    intent = f"{state['action']}_confirmed"
                    intent_response = {
                        "intent": intent,
                        "module": state["module"],
                        "data": data,
                        "reply": "Confirmed. Working on it...",
                        "needs_confirmation": False,
                    }
                    await clear_state(pool)
                    final_reply, reply_markup, _ = await route_intent(
                        pool, intent_response, user_id=telegram_id, bot=context.bot
                    )
                    await update.message.reply_text(
                        final_reply, parse_mode="MarkdownV2", reply_markup=reply_markup
                    )
                    return
                elif any(
                    word in low_text for word in ["no", "stop", "cancel", "don't", "nu"]
                ):
                    await clear_state(pool)
                    await update.message.reply_text("Cancelled\\.")
                    return
                else:
                    await update.message.reply_text(
                        "⚠️ Te rog să confirmi sau să anulezi acțiunea curentă mai întâi (folosind butoanele sau trimițând 'da'/'nu')."
                    )
                    return

            elif state["state_type"] == "awaiting_action_confirm":
                low_text = text.lower()
                if any(
                    word in low_text
                    for word in [
                        "da",
                        "yes",
                        "confirm",
                        "do it",
                        "sure",
                        "ok",
                        "yap",
                        "yep",
                        "yeah",
                    ]
                ):
                    extra = state.get("extra") or {}
                    pending = extra.get("pending_intent", {})
                    await clear_state(pool)
                    if pending:
                        pending["needs_confirmation"] = False
                        pending["_confirmed_bypass"] = True
                        final_reply, reply_markup, _ = await route_intent(
                            pool, pending, user_id=telegram_id, bot=context.bot
                        )
                        await update.message.reply_text(
                            final_reply,
                            parse_mode="MarkdownV2",
                            reply_markup=reply_markup,
                        )
                    return
                elif any(
                    word in low_text
                    for word in [
                        "nu",
                        "no",
                        "cancel",
                        "stop",
                        "anulează",
                        "anuleaza",
                        "anulat",
                    ]
                ):
                    await clear_state(pool)
                    await update.message.reply_text("Anulat. 👌")
                    return
                else:
                    await update.message.reply_text(
                        "⚠️ Te rog să confirmi sau să anulezi acțiunea curentă mai întâi (folosind butoanele sau trimițând 'da'/'nu')."
                    )
                    return

            elif state["state_type"] == "awaiting_profile_hours":
                try:
                    # Handle different dash types (hyphen, en-dash, em-dash)
                    import re

                    parts = re.split(r"[-–—]", text)
                    if len(parts) < 2:
                        raise ValueError("Lipsește separatorul '-'")

                    start_h = parts[0].strip()
                    end_h = parts[1].strip()

                    # Validate format (basic)
                    if ":" not in start_h or ":" not in end_h:
                        raise ValueError("Format invalid: trebuie să conțină ':'")

                    from datetime import datetime

                    start_time = datetime.strptime(start_h, "%H:%M").time()
                    end_time = datetime.strptime(end_h, "%H:%M").time()

                    await pool.execute(
                        "UPDATE user_profile SET active_hours_start = $1, active_hours_end = $2 WHERE telegram_id = $3",
                        start_time,
                        end_time,
                        telegram_id,
                    )
                    await clear_state(pool)
                    await update.message.reply_text(
                        f"✅ Orele active au fost setate la: *{start_h} \\- {end_h}*",
                        parse_mode="MarkdownV2",
                    )
                except Exception as e:
                    pass
                    print(f"ERROR updating profile hours: {e}")
                    traceback.print_exc()
                    await clear_state(pool)
                    await update.message.reply_text(
                        "❌ Format invalid. Încearcă `09:00-21:00`."
                    )
                return

            elif state["state_type"] == "awaiting_clarification":
                # The user is answering a clarification question from a previous low-confidence intent.
                # Merge the clarification answer with the partial intent stored in extra, then re-route.
                extra = state.get("extra") or {}
                partial_intent = extra.get("partial_intent", "")
                partial_data = extra.get("partial_data", {})

                print(
                    f"🔍 CLARIFICATION RECEIVED: '{text}' for partial_intent='{partial_intent}'",
                    flush=True,
                )

                context_snapshot = await build_context(pool, text)
                profile = await get_user_profile(pool, telegram_id)

                # Build an enriched system hint so Gemini knows this is a clarification
                clarification_hint = (
                    f"Utilizatorul răspunde la o întrebare de clarificare. "
                    f"Intent-ul anterior parțial era '{partial_intent}' cu datele: {partial_data}. "
                    f"Combină datele parțiale cu răspunsul utilizatorului și returnează intent-ul complet."
                )

                intent_response = await get_gemini_response(
                    pool,
                    telegram_id,
                    user_message=text,
                    user_name=profile.get("name", "User"),
                    tone=profile.get("tone", "warm"),
                    context_snapshot=context_snapshot,
                    history=history,
                    personal_notes=profile.get("personal_notes") or "",
                    system_hint=clarification_hint,
                    model=profile.get("llm_model"),
                )
                if isinstance(intent_response, dict):
                    intent_response["source"] = source
                    # Merge any partial data that Gemini may have dropped
                    merged_data = {**partial_data, **intent_response.get("data", {})}
                    # Clean internal keys
                    merged_data.pop("_original_reply", None)
                    merged_data.pop("_user_message", None)
                    intent_response["data"] = merged_data
                    # Force confidence=1.0 so we don't loop forever
                    intent_response["confidence"] = 1.0
                    intent_response["clarification_needed"] = False

                await clear_state(pool)
                final_reply, reply_markup, _ = await route_intent(
                    pool, intent_response, user_id=telegram_id, bot=context.bot
                )
                await update.message.reply_text(
                    final_reply, parse_mode="MarkdownV2", reply_markup=reply_markup
                )
                return

            elif state["state_type"] == "awaiting_focus_result":
                session_id = state.get("item_id")
                import db.queries.focus as focus_queries

                if session_id:
                    await focus_queries.complete_session(pool, session_id, text)
                await clear_state(pool)
                await update.message.reply_text(
                    "Notat\\. Sesiune salvată\\. 💪", parse_mode="MarkdownV2"
                )
                return

            elif state["state_type"] == "awaiting_uni_input":
                action = state.get("action")
                if action == "add_subject":
                    from db.queries.university import add_subject

                    await add_subject(pool, text)
                    await clear_state(pool)
                    await update.message.reply_text(
                        f"✅ *{escape_md(text)}* adăugată\\.", parse_mode="MarkdownV2"
                    )
                    return

                elif action == "add_schedule":
                    try:
                        parts = [p.strip() for p in text.split(",")]
                        days_map = {
                            "luni": 0,
                            "marți": 1,
                            "miercuri": 2,
                            "joi": 3,
                            "vineri": 4,
                        }
                        day = days_map.get(parts[0].lower(), 0)
                        times = parts[1].split("-")
                        start_time = times[0].strip()
                        end_time = times[1].strip()
                        subject = parts[2].strip()
                        class_type = parts[3].strip().lower()
                        room = parts[4].strip() if len(parts) > 4 else None
                        week_type = (
                            parts[5].strip().lower() if len(parts) > 5 else "both"
                        )
                        await pool.execute(
                            """
                            INSERT INTO schedule (day_of_week, start_time, end_time, subject_name, class_type, room, week_type)
                            VALUES ($1, $2, $3, $4, $5, $6, $7)
                        """,
                            day,
                            start_time,
                            end_time,
                            subject,
                            class_type,
                            room,
                            week_type,
                        )
                        await clear_state(pool)
                        await update.message.reply_text(
                            "✅ Oră adăugată în orar\\.", parse_mode="MarkdownV2"
                        )
                    except Exception:
                        await clear_state(pool)
                        await update.message.reply_text(
                            "❌ Format greșit\\. Încearcă: `Luni, 08:00\\-09:30, MRU, seminar, 208, odd`",
                            parse_mode="MarkdownV2",
                        )
                    return

                elif action == "add_exam":
                    try:
                        parts = [p.strip() for p in text.split(",")]
                        from db.queries.university import get_subject_by_name, add_exam
                        from datetime import datetime

                        subject = await get_subject_by_name(pool, parts[0])
                        exam_date = datetime.strptime(
                            parts[1].strip(), "%Y-%m-%d"
                        ).date()
                        exam_type = parts[2].strip() if len(parts) > 2 else "examen"
                        room = parts[3].strip() if len(parts) > 3 else None
                        if subject:
                            await add_exam(
                                pool, subject["id"], exam_date, exam_type, room
                            )
                            await clear_state(pool)
                            await update.message.reply_text(
                                "✅ Examen adăugat\\.", parse_mode="MarkdownV2"
                            )
                        else:
                            await clear_state(pool)
                            await update.message.reply_text(
                                f"❌ Materia *{escape_md(parts[0])}* nu e în listă\\.",
                                parse_mode="MarkdownV2",
                            )
                    except Exception:
                        await clear_state(pool)
                        await update.message.reply_text(
                            "❌ Format greșit\\.", parse_mode="MarkdownV2"
                        )
                    return

                elif action == "add_grade":
                    try:
                        parts = [p.strip() for p in text.split(",")]
                        from db.queries.university import get_subject_by_name, add_grade

                        subject = await get_subject_by_name(pool, parts[0])
                        if subject:
                            grade_type = parts[2].strip() if len(parts) > 2 else "exam"
                            await add_grade(
                                pool, subject["id"], float(parts[1]), grade_type
                            )
                            await clear_state(pool)
                            await update.message.reply_text(
                                "✅ Notă adăugată\\.", parse_mode="MarkdownV2"
                            )
                        else:
                            await clear_state(pool)
                            await update.message.reply_text(
                                "❌ Materia nu e în listă\\.", parse_mode="MarkdownV2"
                            )
                    except Exception:
                        await clear_state(pool)
                        await update.message.reply_text(
                            "❌ Format greșit\\.", parse_mode="MarkdownV2"
                        )
                    return

                elif action == "add_attendance":
                    try:
                        parts = [p.strip() for p in text.split(",")]
                        from db.queries.university import (
                            get_subject_by_name,
                            log_attendance,
                        )
                        from datetime import datetime, date as _date

                        subject = await get_subject_by_name(pool, parts[0])
                        attended = parts[1].strip().lower() in [
                            "prezent",
                            "da",
                            "yes",
                            "true",
                        ]
                        att_date = (
                            datetime.strptime(parts[2].strip(), "%Y-%m-%d").date()
                            if len(parts) > 2
                            else _date.today()
                        )
                        if subject:
                            await log_attendance(
                                pool, subject["id"], attended, att_date
                            )
                            await clear_state(pool)
                            status = "prezent ✅" if attended else "absent ❌"
                            await update.message.reply_text(
                                f"{escape_md(subject['name'])} — {status} înregistrat\\.",
                                parse_mode="MarkdownV2",
                            )
                        else:
                            await clear_state(pool)
                            await update.message.reply_text(
                                "❌ Materia nu e în listă\\.", parse_mode="MarkdownV2"
                            )
                    except Exception:
                        await clear_state(pool)
                        await update.message.reply_text(
                            "❌ Format greșit\\.", parse_mode="MarkdownV2"
                        )
                    return

                elif action == "edit_attendance":
                    try:
                        parts = [p.strip() for p in text.split(",")]
                        from db.queries.university import get_subject_by_name
                        from datetime import datetime

                        subject = await get_subject_by_name(pool, parts[0])
                        att_date = datetime.strptime(
                            parts[1].strip(), "%Y-%m-%d"
                        ).date()
                        attended = parts[2].strip().lower() in [
                            "prezent",
                            "da",
                            "yes",
                            "true",
                        ]
                        if subject:
                            await pool.execute(
                                "UPDATE attendances SET attended = $1 WHERE subject_id = $2 AND class_date = $3",
                                attended,
                                subject["id"],
                                att_date,
                            )
                            await clear_state(pool)
                            status = "prezent ✅" if attended else "absent ❌"
                            await update.message.reply_text(
                                f"Prezența actualizată — {status}\\.",
                                parse_mode="MarkdownV2",
                            )
                        else:
                            await clear_state(pool)
                            await update.message.reply_text(
                                "❌ Materia nu e în listă\\.", parse_mode="MarkdownV2"
                            )
                    except Exception:
                        await clear_state(pool)
                        await update.message.reply_text(
                            "❌ Format greșit\\.", parse_mode="MarkdownV2"
                        )
                    return

                elif action == "delete_grade":
                    try:
                        parts = [p.strip() for p in text.split(",")]
                        from db.queries.university import get_subject_by_name

                        subject = await get_subject_by_name(pool, parts[0])
                        grade_type = parts[1].strip() if len(parts) > 1 else None
                        if subject:
                            if grade_type:
                                await pool.execute(
                                    "DELETE FROM grades WHERE subject_id = $1 AND grade_type = $2",
                                    subject["id"],
                                    grade_type,
                                )
                            else:
                                await pool.execute(
                                    "DELETE FROM grades WHERE subject_id = $1",
                                    subject["id"],
                                )
                            await clear_state(pool)
                            await update.message.reply_text(
                                "✅ Notă ștearsă\\.", parse_mode="MarkdownV2"
                            )
                        else:
                            await clear_state(pool)
                            await update.message.reply_text(
                                "❌ Materia nu e în listă\\.", parse_mode="MarkdownV2"
                            )
                    except Exception:
                        await clear_state(pool)
                        await update.message.reply_text(
                            "❌ Format greșit\\.", parse_mode="MarkdownV2"
                        )
                    return

                elif action == "import_schedule_photo":
                    if update.message.photo:
                        photo = update.message.photo[-1]
                        file = await context.bot.get_file(photo.file_id)

                        import tempfile
                        import os

                        with tempfile.NamedTemporaryFile(
                            suffix=".jpg", delete=False
                        ) as tmp:
                            await file.download_to_drive(tmp.name)
                            tmp_path = tmp.name

                        import base64

                        with open(tmp_path, "rb") as f:
                            image_data = base64.b64encode(f.read()).decode()
                        os.unlink(tmp_path)

                        from google.genai import types
                        from core.gemini import client

                        prompt = """
Analizează această imagine cu un orar universitar.
Extrage TOATE cursurile și seminarele vizibile.
Returnează EXCLUSIV JSON valid, fără markdown:
{
  "classes": [
    {
      "day": "Luni|Marți|Miercuri|Joi|Vineri",
      "start_time": "HH:MM",
      "end_time": "HH:MM",
      "subject": "numele materiei",
      "type": "curs|seminar",
      "room": "sala sau null",
      "week_type": "both|odd|even"
    }
  ]
}
week_type: "odd" dacă e marcat SI, "even" dacă SP, "both" dacă apare în ambele sau nu e marcat.
"""
                        response = client.models.generate_content(
                            model="gemini-2.5-flash",
                            contents=[
                                types.Content(
                                    parts=[
                                        types.Part(
                                            inline_data=types.Blob(
                                                mime_type="image/jpeg", data=image_data
                                            )
                                        ),
                                        types.Part(text=prompt),
                                    ]
                                )
                            ],
                        )

                        pass

                        raw = response.text.strip()
                        if "```" in raw:
                            raw = (
                                raw.split("```")[1].lstrip("json").strip().rstrip("```")
                            )

                        try:
                            data_parsed = json.loads(raw)
                            classes = data_parsed.get("classes", [])

                            from db.queries.university_schedules import (
                                insert_schedule_row,
                            )

                            days_map = {
                                "luni": 0,
                                "marți": 1,
                                "miercuri": 2,
                                "joi": 3,
                                "vineri": 4,
                            }
                            imported = 0

                            for c in classes:
                                day = days_map.get(c["day"].lower(), -1)
                                if day == -1:
                                    continue
                                await insert_schedule_row(
                                    pool,
                                    day,
                                    c["start_time"],
                                    c["end_time"],
                                    c["subject"],
                                    c.get("type", "curs"),
                                    c.get("room"),
                                    c.get("week_type", "both"),
                                )
                                imported += 1

                            await clear_state(pool)
                            await update.message.reply_text(
                                f"✅ *{imported} ore importate* din orar\\.\nVerifică cu `/uni` → Orar și ajustează unde este nevoie\\.",
                                parse_mode="MarkdownV2",
                            )
                        except Exception:
                            await clear_state(pool)
                            await update.message.reply_text(
                                "❌ Nu am putut extrage orarul din imagine\\. Încearcă o poză mai clară sau adaugă manual\\.",
                                parse_mode="MarkdownV2",
                            )
                    else:
                        await update.message.reply_text(
                            "Trimite o poză \\(nu text\\) cu orarul tău\\.",
                            parse_mode="MarkdownV2",
                        )
                    return

                elif action == "import_structure_pdf":
                    if (
                        update.message.document
                        and update.message.document.mime_type == "application/pdf"
                    ):
                        file = await context.bot.get_file(
                            update.message.document.file_id
                        )

                        import tempfile
                        import os
                        import base64

                        with tempfile.NamedTemporaryFile(
                            suffix=".pdf", delete=False
                        ) as tmp:
                            await file.download_to_drive(tmp.name)
                            tmp_path = tmp.name

                        with open(tmp_path, "rb") as f:
                            pdf_data = base64.b64encode(f.read()).decode()
                        os.unlink(tmp_path)

                        from google.genai import types
                        from core.gemini import client

                        prompt = """
Analizează acest document cu structura anului universitar.
Extrage TOATE perioadele importante.
Returnează EXCLUSIV JSON valid:
{
  "academic_year": "YYYY-YYYY",
  "semesters": [
    {
      "number": 1,
      "periods": [
        {
          "type": "activitate_didactica|vacanta|sesiune_examene|sesiune_restante",
          "start_date": "YYYY-MM-DD",
          "end_date": "YYYY-MM-DD",
          "description": "descriere scurtă opțională"
        }
      ]
    }
  ]
}
"""
                        response = client.models.generate_content(
                            model="gemini-2.5-flash",
                            contents=[
                                types.Content(
                                    parts=[
                                        types.Part(
                                            inline_data=types.Blob(
                                                mime_type="application/pdf",
                                                data=pdf_data,
                                            )
                                        ),
                                        types.Part(text=prompt),
                                    ]
                                )
                            ],
                        )

                        pass

                        raw = response.text.strip()
                        if "```" in raw:
                            raw = (
                                raw.split("```")[1].lstrip("json").strip().rstrip("```")
                            )

                        try:
                            data_parsed = json.loads(raw)

                            from db.queries.university_schedules import (
                                insert_academic_period,
                            )

                            imported = 0
                            for sem in data_parsed.get("semesters", []):
                                for period in sem.get("periods", []):
                                    from datetime import datetime

                                    await insert_academic_period(
                                        pool,
                                        data_parsed.get("academic_year", "2025-2026"),
                                        sem["number"],
                                        period["type"],
                                        datetime.strptime(
                                            period["start_date"], "%Y-%m-%d"
                                        ).date(),
                                        datetime.strptime(
                                            period["end_date"], "%Y-%m-%d"
                                        ).date(),
                                        period.get("description"),
                                    )
                                    imported += 1

                            await clear_state(pool)
                            await update.message.reply_text(
                                f"✅ *{imported} perioade importate* din structura academică\\.",
                                parse_mode="MarkdownV2",
                            )
                        except Exception:
                            await clear_state(pool)
                            await update.message.reply_text(
                                "❌ Nu am putut extrage structura din PDF\\. Încearcă din nou\\.",
                                parse_mode="MarkdownV2",
                            )
                    else:
                        await update.message.reply_text(
                            "Trimite un fișier PDF \\(nu text\\)\\.",
                            parse_mode="MarkdownV2",
                        )
                    return

            elif state["state_type"] == "awaiting_project_name":
                intent_response = {
                    "intent": "add_project",
                    "module": "projects",
                    "data": {"name": text},
                    "reply": f"Proiectul *{escape_md(text)}* a fost adăugat. ✅",
                    "needs_confirmation": False,
                    "needs_agent": False,
                }
                await clear_state(pool)
                final_reply, reply_markup, _ = await route_intent(
                    pool, intent_response, user_id=telegram_id, bot=context.bot
                )
                if final_reply == "__CONFIRMATION_REQUIRED__":
                    await send_confirmation_request(
                        intent_response.get("intent"),
                        intent_response.get("data") or {},
                        update,
                        context,
                    )
                    return
                await update.message.reply_text(
                    final_reply, parse_mode="MarkdownV2", reply_markup=reply_markup
                )
                return

            elif state["state_type"] == "awaiting_edit_field":
                context_snapshot = await build_context(pool, text)
                profile = await get_user_profile(pool, telegram_id)
                edit_prompt = f"The user wants to edit an item. Module: {state['module']}, Item ID: {state['item_id']}. User input: {text}"

                intent_response = await get_gemini_response(
                    pool,
                    telegram_id,
                    user_message=edit_prompt,
                    user_name=profile.get("name", "User"),
                    tone=profile.get("tone", "warm"),
                    context_snapshot=context_snapshot,
                    history=[],
                    personal_notes=f"ACTION: Extract the fields to change for item {state['item_id']} in module {state['module']}. Return intent='edit_{state['module'][:-1]}', data={{'id': {state['item_id']}, ...fields...}}",
                    system_hint=f"User is editing an item in {state['module']}.",
                    model=profile.get("llm_model"),
                )

                await clear_state(pool)
                final_reply, reply_markup, _ = await route_intent(
                    pool, intent_response, user_id=telegram_id, bot=context.bot
                )
                if final_reply == "__CONFIRMATION_REQUIRED__":
                    await send_confirmation_request(
                        intent_response.get("intent"),
                        intent_response.get("data") or {},
                        update,
                        context,
                    )
                    return
                await update.message.reply_text(
                    final_reply, parse_mode="MarkdownV2", reply_markup=reply_markup
                )
                return

            elif state["state_type"] == "awaiting_day_plan_input":
                # If command, clear state and proceed
                if text.startswith("/"):
                    await clear_state(pool)
                elif any(
                    w in text.lower()
                    for w in [
                        "remintește-mi",
                        "uită-mă",
                        "amintește-mi",
                        "reapă-mă",
                        "setează reminder",
                        "adu-mi aminte",
                        "adumă aminte",
                        "aminteste-mi",
                    ]
                ):
                    # It's a reminder intent - clear state and let normal flow handle it
                    await clear_state(pool)
                else:
                    try:
                        from db.queries.day_plans import save_day_plan
                        from core.gemini import get_proactive_response
                        from datetime import date as _date

                        today = _date.today()
                        profile = await get_user_profile(pool, telegram_id)
                        context_snapshot = await build_context(pool, text)

                        itinerary_instruction = """
Userul a descris cum vrea să-i arate ziua. Pe baza preferințelor lui și a tasks/events/habits din context, generează un itinerar structurat pe ore. 
Format:
🗺 *Planul tău de azi*

08:00 — [activitate]
10:00 — [activitate]
...

Reguli:
- Respectă preferințele userului ca prioritate maximă.
- Integrează events fixe la orele lor exacte din calendar.
- Distribuie tasks și habits în sloturile rămase.
- Fii realist cu timpii (nu supraaglomera).
- Dacă userul nu menționează o activitate din context, integreaz-o natural unde are sens.
- Maxim 8 slots orare.
- Limbă: română, același ton ca restul Lorei.
- Returnează DOAR itinerarul, fără text introductiv.
"""
                        itinerary = await get_proactive_response(
                            itinerary_instruction,
                            f"INPUT USER: {text}\n\nCONTEXT:\n{context_snapshot}",
                        )

                        if itinerary:
                            await save_day_plan(pool, today, text, itinerary)
                            await update.message.reply_text(
                                safe_markdown(itinerary), parse_mode="MarkdownV2"
                            )
                            await clear_state(pool)
                            # Mark plan as done for today
                            from db.queries.profile import update_user_profile

                            await update_user_profile(
                                pool, telegram_id, last_plan_date=today
                            )
                            return
                        else:
                            await update.message.reply_text(
                                "Nu am putut genera planul. Încearcă să-mi dai mai multe detalii."
                            )
                            await clear_state(pool)
                            return

                    except Exception as e:
                        print(f"Error handling day plan input: {e}")
                        traceback.print_exc()
                        err_msg = "Eroare la generarea planului"
                        await update.message.reply_text(err_msg)
                        await clear_state(pool)
                        return

            elif state["state_type"] == "awaiting_evening_response":
                pass
                import textwrap
                from datetime import date as _date, timedelta
                from core.gemini import get_proactive_response
                from db.queries import journal as journal_queries
                from db.queries.day_plans import save_day_plan
                from db.queries.profile import update_user_profile
                from core.config import TELEGRAM_USER_ID as TG_UID

                profile = await get_user_profile(pool, telegram_id)
                today = _date.today()
                tomorrow = today + timedelta(days=1)

                # 1. Extract Reflection, Tomorrow Plan & Wake Time
                extraction_instruction = textwrap.dedent("""
                    Ești Lora, asistenta personală.
                    Userul a răspuns la întrebările de seară (ce a mers bine, ce vrea diferit, plan mâine, oră trezire).
                    Extrage:
                    - reflection_text: rezumat (ce a mers bine + ce ar face diferit) (max 3 propoziții)
                    - mood: great/good/neutral/bad/terrible (pe baza tonului)
                    - tomorrow_plan: ce a zis despre programul de mâine
                    - wake_time: ora de trezire menționată, format HH:MM (ex: "la 7" -> "07:00", "8 jumate" -> "08:30"). Dacă nu e menționată, returnează null.
                    Returnează EXCLUSIV JSON valid:
                    {"reflection_text": "...", "mood": "...", "tomorrow_plan": "...", "wake_time": "..."}
                """).strip()

                raw_extraction = await get_proactive_response(
                    extraction_instruction, text
                )

                try:
                    clean = raw_extraction.strip()
                    if clean.startswith("```"):
                        clean = (
                            clean.split("```")[1].lstrip("json").strip().rstrip("```")
                        )
                    extracted = json.loads(clean)
                    reflection_text = extracted.get("reflection_text", text[:500])
                    mood = extracted.get("mood", "neutral")
                    tomorrow_plan = extracted.get("tomorrow_plan", "")
                    wake_time = extracted.get("wake_time")
                except Exception:
                    reflection_text = text[:500]
                    mood = "neutral"
                    tomorrow_plan = ""
                    wake_time = None

                # 2. Save Journal Entry
                await journal_queries.save_journal_entry(
                    pool, today, reflection_text, mood, tomorrow_plan
                )

                # 3. Generate Tomorrow's Itinerary
                context_snapshot = await build_context(pool, text)

                itinerary_instruction = """
                    Generează un itinerar structurat pe ore pentru MÂINE.
                    Bazează-te pe:
                    1. Planul menționat de user (tomorrow_plan).
                    2. Tasks pending și evenimente din calendar (vezi context).
                    3. Ora de trezire (wake_time).
                    
                    Format:
                    *Mâine:*
                    09:00 — [activitate]
                    11:00 — [activitate]
                    ...
                    
                    Reguli:
                    - Fii realist și echilibrat.
                    - Doar orele și activitățile, maxim 6 sloturi.
                    - Ton cald, Romglish permis.
                    - Returnează DOAR itinerarul.
                """

                itinerary = await get_proactive_response(
                    itinerary_instruction,
                    f" tomorrow_plan: {tomorrow_plan}\n wake_time: {wake_time}\n\nCONTEXT:\n{context_snapshot}",
                )

                if itinerary:
                    await save_day_plan(
                        pool, tomorrow, tomorrow_plan, itinerary, wake_time
                    )

                await clear_state(pool)
                await update_user_profile(pool, TG_UID, last_journal_date=today)

                reply = f"✅ Jurnal salvat\\.\n\n{safe_markdown(itinerary or 'Noapte bună!')}\n\nNoapte bună\\. 🌙"
                await update.message.reply_text(reply, parse_mode="MarkdownV2")
                return

            elif state["state_type"] == "awaiting_task_input":
                # Let it fall through to Gemini with state-based system_hint
                pass

            elif state["state_type"] == "awaiting_project_input":
                from db.queries.projects import add_project
                from core.state import clear_state
                from modules.tasks import get_projects_list_view

                # Check if text contains keywords for other modules - if so, clear state and let Gemini handle it
                lower_text = text.lower()
                other_module_keywords = [
                    "adauga carte",
                    "carte",
                    "book",
                    "reading",
                    "citit",
                    "adauga task",
                    "task",
                    "todo",
                    "workout",
                    "antrenament",
                    "exercitiu",
                    "habit",
                    "obicei",
                    "focus",
                    "pomodoro",
                    "goal",
                    "obiectiv",
                    "skill",
                    "abilitate",
                    "health",
                    "somn",
                    "apa",
                    "greutate",
                    "finance",
                    "cheltuiala",
                    "venit",
                    "mood",
                    "dispozitie",
                ]
                if any(kw in lower_text for kw in other_module_keywords):
                    await clear_state(pool)
                    print(
                        f"🔄 STATE CLEARED: detected other module keyword in '{text}'"
                    )
                    # Fall through to Gemini
                else:
                    # Simple parsing: first line name, rest description
                    lines = text.split("\n")
                    name = lines[0].strip()
                    desc = "\n".join(lines[1:]).strip() if len(lines) > 1 else None

                    await add_project(pool, name, desc)
                    await clear_state(pool)
                    await update.message.reply_text(
                        f"📂 Proiect creat: *{escape_md(name)}*",
                        parse_mode="MarkdownV2",
                    )
                    # Show projects list again
                    text_out, markup = await get_projects_list_view(pool)
                    await update.message.reply_text(
                        text_out, parse_mode="MarkdownV2", reply_markup=markup
                    )
                    return

            elif state["state_type"] == "awaiting_project_edit":
                from modules.tasks import get_project_tasks_view
                from db.queries.projects import update_project

                project_id = state.get("item_id")
                if not project_id:
                    await clear_state(pool)
                    await update.message.reply_text("Eroare: nu am găsit proiectul.")
                    return

                if text.lower() == "delete":
                    from db.queries.projects import delete_project

                    await delete_project(pool, project_id)
                    await clear_state(pool)
                    text_out, markup = await get_projects_list_view(pool)
                    await update.message.reply_text(
                        f"🗑️ Proiect șters\\.\n\n{text_out}",
                        parse_mode="MarkdownV2",
                        reply_markup=markup,
                    )
                    return

                await update_project(pool, project_id, description=text)
                await clear_state(pool)
                text_out, markup = await get_project_tasks_view(pool, project_id)
                await update.message.reply_text(
                    f"✅ Descriere actualizată\\.\n\n{text_out}",
                    parse_mode="MarkdownV2",
                    reply_markup=markup,
                )
                return

            elif state["state_type"] == "awaiting_event_note":
                from datetime import datetime

                event_id = state.get("item_id")
                if event_id and text:
                    await update.message.reply_text("Notă adăugată pentru eveniment 📝")
                await clear_state(pool)
                return

            elif state["state_type"] in [
                "awaiting_health_input",
                "awaiting_finance_input",
                "awaiting_workout_input",
            ]:
                if state["module"] == "health":
                    from modules.health import handle_health_message

                    await handle_health_message(update, pool, state, text)
                elif state["module"] == "finance":
                    from modules.finance import handle_finance_message

                    await handle_finance_message(update, pool, state, text)
                elif state["module"] == "workout":
                    from modules.workout import handle_workout_message

                    await handle_workout_message(update, pool, state, text)

                # Fall through to Gemini if not returned by handlers
                await clear_state(pool)

        intent_response = None
        low_text = text.lower()

        # 5. Fall back to Gemini if regex didn't match
        if not intent_response:
            print("⏳ BUILDING CONTEXT (Lazy Load)...", flush=True)
            context_snapshot = await build_context(pool, text)
            profile = await get_user_profile(pool, telegram_id)

            # Generate hint based on state
            system_hint = ""
            if state:
                state_type = state.get("state_type")
                if state_type == "awaiting_task_input":
                    system_hint = "User is providing the TITLE for a new TASK. Extract it as add_task."
                elif state_type == "awaiting_project_input":
                    system_hint = "User is providing info for a new PROJECT. Extract it as add_project."
                elif state_type == "awaiting_health_input":
                    system_hint = "User is providing health/metric data. Extract it as health_log."
                elif state_type == "awaiting_skill_input":
                    system_hint = (
                        "User is logging skill progress. Extract it as log_skill."
                    )
                elif state_type == "awaiting_finance_input":
                    system_hint = (
                        "User is providing finance data. Extract it as finance_log."
                    )
                elif state_type == "awaiting_uni_input":
                    system_hint = (
                        "User is providing university data (exam, grade, or subject)."
                    )

            intent_response = await get_gemini_response(
                pool,
                telegram_id,
                user_message=text,
                user_name=profile.get("name", "User"),
                tone=profile.get("tone", "warm"),
                context_snapshot=context_snapshot,
                history=history,
                personal_notes=profile.get("personal_notes") or "",
                system_hint=system_hint,
                voice_uri=voice_uri,
                model=profile.get("llm_model"),
            )
            # Stamp the source so the router can pass it through
            if isinstance(intent_response, dict):
                intent_response["source"] = source
        else:
            # For regex matches, we might still need the profile for trigger_morning_briefing
            # but we can load it only if that specific intent is found later.
            # For now, let's keep it minimal.
            pass
        print(
            f"🧠 GEMINI: Intent={intent_response.get('intent')}, Module={intent_response.get('module')}, Data={intent_response.get('data')}"
        )

        # Special handling for morning briefing - call directly with application
        if intent_response.get("intent") == "trigger_morning_briefing":
            from scheduler.jobs import send_morning_briefing
            from core.config import TELEGRAM_USER_ID as TG_UID
            import db.queries.profile as profile_queries
            from datetime import date as _date

            today = _date.today()
            profile = await profile_queries.get_user_profile(pool, TG_UID)
            if profile.get("last_briefing_date") == today:
                await update.message.reply_text(
                    safe_markdown(
                        "Deja ți-am trimis briefing-ul de dimineață. O zi productivă! ☀️"
                    ),
                    parse_mode="MarkdownV2",
                )
                return

            await update.message.reply_text(
                safe_markdown("Pregătesc briefing-ul de dimineață. ☕"),
                parse_mode="MarkdownV2",
            )
            try:
                await send_morning_briefing(context.application, pool, force=True)
            except Exception as e:
                pass

                print(f"ERROR in morning briefing: {e}", flush=True)
                traceback.print_exc()
                await update.message.reply_text(
                    safe_markdown(f"❌ Eroare la briefing: {str(e)[:200]}"),
                    parse_mode="MarkdownV2",
                )
            return

        # 5. Merge state context into Gemini results
        if state:
            state_type = state.get("state_type")
            if state_type == "awaiting_task_input":
                # If Gemini somehow failed to catch add_task despite hint, force it here
                if intent_response.get("intent") != "add_task":
                    intent_response["intent"] = "add_task"
                    intent_response["module"] = "tasks"
                    if not intent_response.get("data"):
                        intent_response["data"] = {}
                    if not intent_response["data"].get("title"):
                        intent_response["data"]["title"] = text

                # Ensure project_id is preserved if it came from state
                project_id = state.get("extra")
                if project_id:
                    if not intent_response.get("data"):
                        intent_response["data"] = {}
                    intent_response["data"]["project_id"] = project_id

            elif state_type == "awaiting_project_input":
                if intent_response.get("intent") != "add_project":
                    intent_response["intent"] = "add_project"
                    intent_response["module"] = "projects"
                    if not intent_response.get("data"):
                        intent_response["data"] = {}
                    if not intent_response["data"].get("name"):
                        intent_response["data"]["name"] = text

        # 6. Clear state before routing if we processed a state-based intent
        if state and intent_response.get("intent") in [
            "add_task",
            "add_project",
            "health_log",
            "log_skill",
            "finance_log",
        ]:
            from core.state import clear_state

            await clear_state(pool)

        # 7. Route intent and get final reply + keyboard
        intent_response["_user_message"] = text
        final_reply, reply_markup, _ = await route_intent(
            pool, intent_response, user_id=telegram_id, bot=context.bot
        )
        if final_reply == "__CONFIRMATION_REQUIRED__":
            await send_confirmation_request(
                intent_response.get("intent"),
                intent_response.get("data") or {},
                update,
                context,
            )
            return
        print(f"📡 ROUTER: Reply length={len(final_reply) if final_reply else 0}")

        if not final_reply or str(final_reply).strip() == "":
            print(
                "⚠️ Router returned empty reply, sending generic fallback...", flush=True
            )
            final_reply = "Scuze, nu am înțeles. (Răspuns gol de la LLM)"
        await save_message(pool, telegram_id, "assistant", final_reply)

        # 7. Send to user
        chunks = split_message(final_reply)

        # If input was voice, send a voice reply first (or along with text)
        if (
            source == "voice" and final_reply and len(final_reply) < 1000
        ):  # Don't TTS very long messages
            try:
                from bot.tts import text_to_speech

                print(f"🎙️ Generating voice reply for {telegram_id}...", flush=True)
                voice_path = await text_to_speech(final_reply)
                if voice_path and os.path.exists(voice_path):
                    with open(voice_path, "rb") as f:
                        await update.message.reply_voice(voice=f, caption="Lora 🎙️")
                    os.remove(voice_path)
            except Exception as tts_err:
                print(f"❌ TTS ERROR: {tts_err}")

        for i, chunk in enumerate(chunks):
            current_markup = reply_markup if i == len(chunks) - 1 else None
            try:
                print(
                    f"📤 SENDING chunk {i + 1}/{len(chunks)}: {repr(chunk[:50])}...",
                    flush=True,
                )
                await update.message.reply_text(
                    safe_markdown(chunk),
                    parse_mode="MarkdownV2",
                    reply_markup=current_markup,
                )

            except Exception as e:
                print(
                    f"⚠️ MarkdownV2 FAILED for chunk {i + 1}, falling back to plain text: {e}",
                    flush=True,
                )
                try:
                    await update.message.reply_text(chunk, reply_markup=current_markup)
                except Exception as e2:
                    print(f"🚨 Plain text fallback ALSO FAILED: {e2}", flush=True)
                    raise e2

    except Exception as e:
        pass
        pass

        logger = logging.getLogger(__name__)
        logger.error(f"ERROR in message_handler: {e}\n{traceback.format_exc()}")
        try:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Ceva n-a mers. Încearcă din nou.",
            )
        except Exception:
            pass


async def handle_confirmation_callback(query, pool, action_type: str, bot) -> None:
    """Helper function to handle confirmation callbacks (HITL Gate)."""
    from core.state import get_state, clear_state

    telegram_id = query.from_user.id

    if action_type == "confirm":
        state = await get_state(pool)
        if state and state["state_type"] == "awaiting_action_confirm":
            extra = state.get("extra") or {}
            pending = extra.get("pending_intent", {})
            await clear_state(pool)
            if pending:
                pending["needs_confirmation"] = False
                pending["_confirmed_bypass"] = True
                from core.router import route_intent

                final_reply, reply_markup, _ = await route_intent(
                    pool, pending, user_id=telegram_id, bot=bot
                )
                await query.edit_message_text(
                    final_reply, parse_mode="MarkdownV2", reply_markup=reply_markup
                )
    elif action_type == "cancel":
        await clear_state(pool)
        await query.edit_message_text("Anulat. 👌")


async def handle_new_confirmation_callback(query, pool, callback_data: str, bot) -> None:
    """Handles new style confirmation callbacks (conf_yes / conf_no)."""
    from core.state import get_pending_action, clear_pending_action

    telegram_id = query.from_user.id

    if callback_data == "conf_yes":
        pending = await get_pending_action(pool)
        if pending:
            intent = pending.get("intent")
            module = pending.get("module")
            payload = pending.get("payload") or {}

            # Construct intent response for routing with bypass
            intent_response = {
                "intent": intent,
                "module": module,
                "data": payload,
                "needs_confirmation": False,
                "_confirmed_bypass": True,
            }

            # Clear state first
            await clear_pending_action(pool)

            from core.router import route_intent

            final_reply, reply_markup, _ = await route_intent(
                pool, intent_response, user_id=telegram_id, bot=bot
            )

            # Send message
            success_msg = f"*Acțiune executată cu succes\\!* ✨\n\n{final_reply}"
            await query.edit_message_text(
                success_msg, parse_mode="MarkdownV2", reply_markup=reply_markup
            )
        else:
            await query.edit_message_text("Nu am găsit nicio acțiune în așteptare. ❌")

    elif callback_data == "conf_no":
        await clear_pending_action(pool)
        await query.edit_message_text("Acțiune anulată.")


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, pool):
    query = update.callback_query
    await query.answer()

    if not await security_check(update):
        return

    try:
        data = query.data
        if data in ("conf_yes", "conf_no"):
            await handle_new_confirmation_callback(query, pool, data, context.bot)
            return

        from bot.callback_utils import parse_callback_data

        action, params = parse_callback_data(data)

        print(
            f"DEBUG: CALLBACK RECEIVED: action={action} params={params} from user={update.effective_user.id}",
            flush=True,
        )

        if action == "action":
            action_type = params[0] if params else ""
            await handle_confirmation_callback(query, pool, action_type, context.bot)
            return

        if action == "task":
            task_action = params[0] if params else ""
            if task_action == "reschedule":
                task_id = int(params[1])
                await pool.execute(
                    "UPDATE tasks SET due_date = CURRENT_DATE + INTERVAL '1 day', updated_at = NOW() WHERE id = $1",
                    task_id,
                )
                await query.answer("Task reprogramat!")
                await query.edit_message_text("Am reprogramat task-ul pentru mâine. 📅")
                return
            elif task_action == "ignore":
                await query.answer("Ignorat.")
                await query.edit_message_text("Ignorat. 👌")
                return

        if action == "habit":
            habit_action = params[0] if params else ""
            if habit_action == "log_yesterday":
                from datetime import date, timedelta

                habit_id = int(params[1])
                yesterday = date.today() - timedelta(days=1)
                async with pool.acquire() as conn:
                    exists = await conn.fetchval(
                        "SELECT EXISTS(SELECT 1 FROM habit_logs WHERE habit_id = $1 AND log_date = $2)",
                        habit_id,
                        yesterday,
                    )
                    if not exists:
                        await conn.execute(
                            "INSERT INTO habit_logs (habit_id, log_date, status) VALUES ($1, $2, 'done')",
                            habit_id,
                            yesterday,
                        )
                await query.answer("Habit logat!")
                await query.edit_message_text(
                    "Habit-ul de ieri a fost logat ca completat. ✅"
                )
                return
            elif habit_action == "ignore":
                await query.answer("Ignorat.")
                await query.edit_message_text("Ignorat. 👌")
                return

        if data.startswith("profile_"):
            if data == "profile_edit_tone":
                pass

                keyboard = [
                    [
                        InlineKeyboardButton(
                            "😊 Warm", callback_data="profile_set_tone:warm"
                        ),
                        InlineKeyboardButton(
                            "🎯 Direct", callback_data="profile_set_tone:direct"
                        ),
                        InlineKeyboardButton(
                            "⚡ Brief", callback_data="profile_set_tone:brief"
                        ),
                    ]
                ]
                await query.edit_message_text(
                    "Alege noul ton pentru Lora:",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                )
            elif data.startswith("profile_set_tone:"):
                new_tone = data.split(":")[1]
                await pool.execute(
                    "UPDATE user_profile SET tone = $1 WHERE telegram_id = $2",
                    new_tone,
                    update.effective_user.id,
                )
                await query.edit_message_text(
                    f"✅ Tonul a fost setat la: *{new_tone}*", parse_mode="MarkdownV2"
                )
            elif data == "profile_edit_hours":
                from core.state import set_state

                await set_state(
                    pool, "awaiting_profile_hours", "profile", "edit_hours", None
                )
                await query.edit_message_text(
                    "Te rog introdu intervalul de ore active \\(ex: `09:00-21:00`\\):",
                    parse_mode="MarkdownV2",
                )
            return

        if data.startswith("memory:"):
            from modules.memory import handle_memory_callback

            await handle_memory_callback(query, pool, data)
            return

        if data.startswith("vision:"):
            from core.vision import handle_vision_callback

            await handle_vision_callback(query, pool, data)
            return
        if data.startswith("chat:"):
            # Global chat-related callbacks (like 'Back to Main')
            if data == "chat:main":
                from core.router import main_menu_keyboard

                await query.edit_message_text(
                    "Meniu Principal 🏠", reply_markup=main_menu_keyboard()
                )
            return

        if data.startswith("eod:"):
            await handle_eod_callback(query, pool, data)
            return
        if data.startswith("goals_"):
            from modules.goals import handle_goals_callback

            await handle_goals_callback(query, pool, data)
            return

        if data.startswith("skills_"):
            from modules.skills import handle_skills_callback

            await handle_skills_callback(update, context, pool)
            return

        if data.startswith("reading_"):
            from modules.reading import handle_reading_callback

            await handle_reading_callback(query, pool, data)
            return

        if data.startswith("workout_"):
            from modules.workout import handle_workout_callback

            await handle_workout_callback(query, pool, data)
            return

        if data.startswith("tasks:") or data.startswith("projects:"):
            from modules.tasks import handle_tasks_callback

            await handle_tasks_callback(query, pool, data)
            return

        if data.startswith("health:"):
            from modules.health import handle_health_callback

            await handle_health_callback(query, pool, data)
            return

        if data.startswith("travel:"):
            from modules.travel import handle_travel_callback

            await handle_travel_callback(query, pool, data)
            return

        if data.startswith("uni:"):
            await handle_uni_callback(query, pool, data)
            return

        if data.startswith("attendance:"):
            from db.queries.university import log_attendance_by_schedule

            # Format: attendance:present:schedule_id
            if len(params) >= 2:
                status = params[0] == "present"
                schedule_id = int(params[1])
                await log_attendance_by_schedule(pool, schedule_id, status)
                msg = "✅ Prezență salvată" if status else "❌ Absență salvată"
                await query.answer(msg)
                await query.edit_message_text(f"{msg} (confirmat)")
            return

        if (
            action == "finance"
            or action == "finance_chart"
            or action == "finance_summary"
        ):
            import io
            from modules.finance import handle_finance_intent

            if data == "finance_chart" or action == "finance_chart":
                result, _, _ = await handle_finance_intent(pool, "finance_chart", {})
                if isinstance(result, (bytes, io.BytesIO)):
                    await context.bot.send_photo(
                        chat_id=update.effective_chat.id,
                        photo=result,
                        caption="Finance Trends 📉 (ultimele 30 zile)",
                    )
                else:
                    await query.message.reply_text(result)
                return

            elif data == "finance_summary" or action == "finance_summary":
                text, markup, _ = await handle_finance_intent(
                    pool, "finance_summary", {}
                )
                await query.edit_message_text(
                    text, parse_mode="MarkdownV2", reply_markup=markup
                )
                return

            elif data == "finance_add_expense":
                from core.state import set_state

                await set_state(
                    pool,
                    "awaiting_finance_input",
                    "finance",
                    "finance_log",
                    None,
                    {"type": "expense"},
                )
                prompt = "💸 *Ce cheltuială ai făcut?*\n_\\(ex: 50 RON cafea, taxi 30lei, mâncare 100\\)_"
                await query.edit_message_text(prompt, parse_mode="MarkdownV2")
                await _save_prompt_to_conversation(pool, prompt)
                return

            elif data == "finance_add_income":
                from core.state import set_state

                await set_state(
                    pool,
                    "awaiting_finance_input",
                    "finance",
                    "finance_log",
                    None,
                    {"type": "income"},
                )
                prompt = "💰 *Ce venit ai primit?*\n_\\(ex: salariu 5000, bonus 200, vânzare olx 50\\)_"
                await query.edit_message_text(prompt, parse_mode="MarkdownV2")
                await _save_prompt_to_conversation(pool, prompt)
                return

            elif data == "finance_stats":
                await query.answer(
                    "Statisticile detaliate sunt în curs de implementare... 🚧"
                )
                return

            elif data == "finance_categories":
                text, markup, _ = await handle_finance_intent(
                    pool, "list_categories", {}
                )
                await query.edit_message_text(
                    text, parse_mode="MarkdownV2", reply_markup=markup
                )
                return

            elif data == "finance_add_category":
                from core.state import set_state

                await set_state(
                    pool,
                    "awaiting_finance_input",
                    "finance",
                    "add_category",
                    None,
                )
                prompt = "💰 *Nume pentru categorie nouă:*\n_(ex: cafea, combustibil, abonamente)_"
                await query.edit_message_text(prompt, parse_mode="MarkdownV2")
                await _save_prompt_to_conversation(pool, prompt)
                return

            return

        # Event Reminders
        if data.startswith("event_reminder:"):
            parts = data.split(":")
            if len(parts) >= 3:
                event_id = int(parts[1])
                minutes = int(parts[2])
                from db.queries.events import update_event_reminder

                await update_event_reminder(pool, event_id, minutes)

                if minutes == 0:
                    msg = "Reminder dezactivat 🔕"
                elif minutes == 1440:
                    msg = "Reminder setat la 1 zi 📅"
                else:
                    msg = f"Reminder setat la {minutes} minute 🔔"

                await query.answer(msg)
                await query.edit_message_text(msg)
            return

        if data.startswith("event_reminder_ack:"):
            event_id = data.split(":")[1]
            await query.answer("Ok 👍")
            await query.edit_message_text("Reminder confirmat 👍")
            return

        if data.startswith("event_note:"):
            event_id = data.split(":")[1]
            from core.state import set_state

            await set_state(
                pool, "awaiting_event_note", "events", "add_note", int(event_id)
            )
            await query.edit_message_text(
                "Ce note vrei să adaugi pentru acest eveniment?"
            )
            return

        if data == "event_day_ack":
            await query.answer("Ok 👍")
            await query.edit_message_text("Reminder 1 zi confirmat 👍")
            return

        # Tasks and projects are handled by handle_tasks_callback (set above)
        # Generic cancel action
        if data in ["cancel", "delete_cancelled"]:
            from core.state import clear_state

            await clear_state(pool)
            await query.edit_message_text("Action cancelled\\.")
            return

        # Generic fallback for unknown callbacks
        import logging

        logger = logging.getLogger(__name__)
        logger.warning(
            f"Unknown callback data received: action={action} params={params} (raw: {data})"
        )
        await query.message.reply_text(
            "Scuze, această acțiune nu mai este valabilă sau a apărut o eroare internă."
        )

    except Exception as e:
        print(f"ERROR in callback_handler: {e}")
        traceback.print_exc()


async def show_uni_dashboard(message_or_query, pool, send_new: bool = False):
    """Renders the /uni academic dashboard."""
    from db.queries.schedule import get_current_week_type
    from db.queries.university import get_general_average, get_attendance_warnings
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton

    week_type = await get_current_week_type(pool)
    week_label = "impară" if week_type == "odd" else "pară"

    config = await pool.fetchrow(
        "SELECT semester_start FROM semester_config ORDER BY id DESC LIMIT 1"
    )
    week_num = 1
    if config:
        delta = (date.today() - config["semester_start"]).days
        week_num = delta // 7 + 1

    avg = await get_general_average(pool)
    warnings = await get_attendance_warnings(pool)

    avg_str = f"*{avg}*" if avg else "—"
    warn_str = f"⚠️ {len(warnings)} materii sub minim" if warnings else "✅ Toate ok"

    text = (
        f"🎓 *Viața Academică*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📅 Semestrul II — săptămâna *{week_num}* \\({escape_md(week_label)}\\)\n"
        f"📊 Medie generală: {avg_str}\n"
        f"👁 Prezențe: {escape_md(warn_str)}\n"
    )

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "📊 Overview", callback_data=make_callback_data("uni", "overview")
                ),
                InlineKeyboardButton(
                    "📚 Materii", callback_data=make_callback_data("uni", "subjects")
                ),
            ],
            [
                InlineKeyboardButton(
                    "📅 Orar", callback_data=make_callback_data("uni", "schedule")
                ),
                InlineKeyboardButton(
                    "🎓 Examene", callback_data=make_callback_data("uni", "exams")
                ),
            ],
            [
                InlineKeyboardButton(
                    "📝 Note & Prezențe",
                    callback_data=make_callback_data("uni", "grades"),
                )
            ],
            [
                InlineKeyboardButton(
                    "🔍 Analiză", callback_data=make_callback_data("uni", "analysis")
                ),
                InlineKeyboardButton(
                    "📥 Import", callback_data=make_callback_data("uni", "import")
                ),
            ],
        ]
    )

    if send_new:
        await message_or_query.reply_text(
            text, parse_mode="MarkdownV2", reply_markup=keyboard
        )
    else:
        await message_or_query.edit_message_text(
            text, parse_mode="MarkdownV2", reply_markup=keyboard
        )


async def handle_uni_callback(query, pool, data: str):
    """Routes all uni: callback queries."""
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    import traceback
    from bot.formatter import safe_markdown

    try:
        await query.answer()
        parts = data.split(":")
        section = parts[1] if len(parts) > 1 else ""
        action = parts[2] if len(parts) > 2 else ""
        item_id = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else None

        back_btn = InlineKeyboardButton(
            "← Înapoi", callback_data=make_callback_data("uni", "dashboard")
        )

        # ━━━ DASHBOARD ━━━
        if section == "dashboard":
            await show_uni_dashboard(query, pool, send_new=False)
            return

        # ━━━ OVERVIEW ━━━
        elif section == "overview":
            from db.queries.schedule import get_today_schedule, get_current_week_type
            from db.queries.university import list_subjects, get_upcoming_exams
            from datetime import date

            week_type = await get_current_week_type(pool)
            week_label = "impară" if week_type == "odd" else "pară"
            config = await pool.fetchrow(
                "SELECT semester_start FROM semester_config ORDER BY id DESC LIMIT 1"
            )
            week_num = 1
            if config:
                delta = (date.today() - config["semester_start"]).days
                week_num = delta // 7 + 1

            classes_today = await get_today_schedule(pool)
            subjects = await list_subjects(pool)
            exams = await get_upcoming_exams(pool, days=14)

            lines = ["📊 *Overview Academic*\n"]
            lines.append(f"📅 Săptămâna *{week_num}* \\({escape_md(week_label)}\\)")
            lines.append(f"📚 Materii active: *{len(subjects)}*\n")

            if classes_today:
                lines.append("*Azi la facultate:*")
                for c in classes_today:
                    start = c["start_time"].strftime("%H:%M")
                    icon = "📖" if c["class_type"] == "curs" else "✏️"
                    room = f" · {escape_md(c['room'])}" if c.get("room") else ""
                    lines.append(
                        f"{icon} `{start}` {escape_md(c['subject_name'])}{room}"
                    )
            else:
                lines.append("✅ Nu ai cursuri azi\\.")

            if exams:
                lines.append("\n*Examene în 14 zile:*")
                for e in exams[:3]:
                    lines.append(
                        f"• {escape_md(e['exam_date'].strftime('%d %b'))} — {escape_md(e['subject_name'])}"
                    )

            keyboard = InlineKeyboardMarkup([[back_btn]])
            await query.edit_message_text(
                "\n".join(lines), parse_mode="MarkdownV2", reply_markup=keyboard
            )

        # ━━━ MATERII ━━━
        elif section == "subjects":
            if not action:
                from db.queries.university import list_subjects

                subjects = await list_subjects(pool)

                lines = [
                    "📚 *Materii*\n",
                    "Alege o materie pentru detalii sau ștergere:",
                ]

                keyboard_rows = []
                for s in subjects:
                    name = s["name"]
                    # Scurtăm numele dacă e prea lung pentru buton
                    btn_text = (name[:25] + "..") if len(name) > 27 else name
                    keyboard_rows.append(
                        [
                            InlineKeyboardButton(
                                btn_text,
                                callback_data=make_callback_data(
                                    "uni", "subjects", "view", s["id"]
                                ),
                            )
                        ]
                    )

                # Adăugăm butonul de adăugare la final
                keyboard_rows.append(
                    [
                        InlineKeyboardButton(
                            "➕ Adaugă materie nouă",
                            callback_data=make_callback_data("uni", "subjects", "add"),
                        )
                    ]
                )
                keyboard_rows.append([back_btn])

                await query.edit_message_text(
                    "\n".join(lines),
                    parse_mode="MarkdownV2",
                    reply_markup=InlineKeyboardMarkup(keyboard_rows),
                )

            elif action == "view" and item_id:
                from db.queries.university import get_subject_by_id, get_subject_details

                subject = await get_subject_by_id(pool, item_id)
                if not subject:
                    await query.answer("Materia nu a fost găsită.")
                    return

                details = await get_subject_details(pool, item_id)

                lines = [f"📚 *{escape_md(subject['name'])}*\n"]
                if subject["professor"]:
                    lines.append(f"👨‍🏫 Prof: {escape_md(subject['professor'])}")
                if subject["credits"]:
                    lines.append(f"💎 Credite: {subject['credits']}")

                att = details.get("attendance", {})
                attended = att.get("attended", 0)
                total = att.get("total", 0)
                lines.append(f"\n✅ Prezențe: {attended}/{total}")

                avg = details.get("avg_grade")
                if avg:
                    lines.append(f"⭐ Medie: {avg}")

                keyboard = InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "🗑️ Șterge",
                                callback_data=make_callback_data(
                                    "uni", "subjects", "delete", item_id
                                ),
                            ),
                            InlineKeyboardButton(
                                "🔙 Înapoi",
                                callback_data=make_callback_data("uni", "subjects"),
                            ),
                        ]
                    ]
                )

                await query.edit_message_text(
                    "\n".join(lines), parse_mode="MarkdownV2", reply_markup=keyboard
                )

            elif action == "delete" and item_id:
                from db.queries.university import delete_subject, get_subject_by_id

                subject = await get_subject_by_id(pool, item_id)
                await delete_subject(pool, item_id)

                await query.answer("Materia a fost ștearsă.")
                # Redirijăm către listă
                await handle_uni_callback(query, pool, "uni:subjects")

            elif action == "add":
                from core.state import set_state

                await set_state(
                    pool, "awaiting_uni_input", "university", "add_subject", None
                )
                keyboard = InlineKeyboardMarkup([[back_btn]])
                prompt = "📚 *Adaugă materie*\n\nScrie numele materiei:"
                await query.edit_message_text(
                    prompt,
                    parse_mode="MarkdownV2",
                    reply_markup=keyboard,
                )
                await _save_prompt_to_conversation(pool, prompt)

        # ━━━ ORAR ━━━
        elif section == "schedule":
            if not action:
                from db.queries.schedule import get_week_schedule, get_current_week_type

                week_schedule, days, week_type = await get_week_schedule(pool)
                week_label = "impară" if week_type == "odd" else "pară"

                lines = [f"📅 *Orar — săptămână {escape_md(week_label)}*\n"]
                for day_idx, day_name in days.items():
                    classes = week_schedule.get(day_idx, [])
                    if not classes:
                        continue
                    lines.append(f"*{escape_md(day_name)}*")
                    for c in classes:
                        start = c["start_time"].strftime("%H:%M")
                        icon = "📖" if c["class_type"] == "curs" else "✏️"
                        room = f" · {escape_md(c['room'])}" if c.get("room") else ""
                        lines.append(
                            f"  {icon} `{start}` {escape_md(c['subject_name'])}{room}"
                        )
                    lines.append("")

                keyboard = InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "➕ Adaugă oră",
                                callback_data=make_callback_data(
                                    "uni", "schedule", "add"
                                ),
                            )
                        ],
                        [back_btn],
                    ]
                )
                await query.edit_message_text(
                    "\n".join(lines), parse_mode="MarkdownV2", reply_markup=keyboard
                )

            elif action == "add":
                from core.state import set_state

                await set_state(
                    pool, "awaiting_uni_input", "university", "add_schedule", None
                )
                keyboard = InlineKeyboardMarkup([[back_btn]])
                prompt = (
                    "📅 *Adaugă oră în orar*\n\n"
                    "Scrie în format:\n"
                    "`Zi, HH:MM\\-HH:MM, Materie, tip, sala, sapt`\n\n"
                    "Exemplu: `Luni, 08:00\\-09:30, MRU, seminar, 208, odd`"
                )
                await query.edit_message_text(
                    prompt,
                    parse_mode="MarkdownV2",
                    reply_markup=keyboard,
                )
                await _save_prompt_to_conversation(pool, prompt)

        # ━━━ EXAMENE ━━━
        elif section == "exams":
            if not action:
                from db.queries.university import get_upcoming_exams

                exams = await get_upcoming_exams(pool, days=90)

                if not exams:
                    text_msg = "🎓 *Examene*\n\nNiciun examen înregistrat\\."
                else:
                    lines = ["🎓 *Examene upcoming*\n"]
                    for e in exams:
                        date_str = escape_md(e["exam_date"].strftime("%d %b %Y"))
                        subject = escape_md(e["subject_name"])
                        type_str = escape_md(e.get("exam_type", "examen"))
                        loc = f" · {escape_md(e['room'])}" if e.get("room") else ""
                        lines.append(
                            f"• *{date_str}* — {subject} \\({type_str}\\){loc}"
                        )
                    text_msg = "\n".join(lines)

                keyboard = InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "➕ Adaugă examen",
                                callback_data=make_callback_data("uni", "exams", "add"),
                            )
                        ],
                        [back_btn],
                    ]
                )
                await query.edit_message_text(
                    text_msg, parse_mode="MarkdownV2", reply_markup=keyboard
                )

            elif action == "add":
                from core.state import set_state

                await set_state(
                    pool, "awaiting_uni_input", "university", "add_exam", None
                )
                keyboard = InlineKeyboardMarkup([[back_btn]])
                prompt = (
                    "🎓 *Adaugă examen*\n\n"
                    "Scrie în format:\n"
                    "`Materie, YYYY\\-MM\\-DD, tip, sala`\n\n"
                    "Exemplu: `Statistică, 2026\\-06\\-15, examen, A2`"
                )
                await query.edit_message_text(
                    prompt,
                    parse_mode="MarkdownV2",
                    reply_markup=keyboard,
                )
                await _save_prompt_to_conversation(pool, prompt)

        # ━━━ NOTE & PREZENȚE ━━━
        elif section == "grades":
            if not action:
                from db.queries.university import list_subjects

                subjects = await list_subjects(pool)

                lines = ["📝 *Note \\& Prezențe*\n"]
                for s in subjects:
                    name = escape_md(s["name"])

                    # Note: — (or grade)
                    avg_val = s.get("avg_grade")
                    avg_str = f"*{avg_val}*" if avg_val else "—"

                    # Prezențe: 3/7 (or —)
                    attended = s.get("attended_count") or 0
                    total = s.get("total_seminars") or 0
                    pres_str = f"{attended}/{total}" if total > 0 else "—"

                    lines.append(
                        f"*{name}*\nNote: {avg_str}\nPrezențe: {escape_md(pres_str)}"
                    )

                keyboard = InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "➕ Notă",
                                callback_data=make_callback_data(
                                    "uni", "grades", "add_grade"
                                ),
                            ),
                            InlineKeyboardButton(
                                "➕ Prezență",
                                callback_data=make_callback_data(
                                    "uni", "grades", "add_attendance"
                                ),
                            ),
                        ],
                        [
                            InlineKeyboardButton(
                                "✏️ Edit prezență",
                                callback_data=make_callback_data(
                                    "uni", "grades", "edit_attendance"
                                ),
                            ),
                            InlineKeyboardButton(
                                "🗑 Șterge notă",
                                callback_data=make_callback_data(
                                    "uni", "grades", "delete_grade"
                                ),
                            ),
                        ],
                        [back_btn],
                    ]
                )
                await query.edit_message_text(
                    "\n".join(lines), parse_mode="MarkdownV2", reply_markup=keyboard
                )

            elif action == "add_grade":
                from core.state import set_state

                await set_state(
                    pool, "awaiting_uni_input", "university", "add_grade", None
                )
                keyboard = InlineKeyboardMarkup([[back_btn]])
                prompt = "📝 *Adaugă notă*\n\nFormat: `Materie, notă, tip`\nExemplu: `Statistică, 8\\.5, partial`"
                await query.edit_message_text(
                    prompt,
                    parse_mode="MarkdownV2",
                    reply_markup=keyboard,
                )
                await _save_prompt_to_conversation(pool, prompt)

            elif action == "add_attendance":
                from core.state import set_state

                await set_state(
                    pool, "awaiting_uni_input", "university", "add_attendance", None
                )
                keyboard = InlineKeyboardMarkup([[back_btn]])
                prompt = "📝 *Adaugă prezență*\n\nFormat: `Materie, prezent/absent, YYYY\\-MM\\-DD`\nExemplu: `MRU, prezent, 2026\\-03\\-23`"
                await query.edit_message_text(
                    prompt,
                    parse_mode="MarkdownV2",
                    reply_markup=keyboard,
                )
                await _save_prompt_to_conversation(pool, prompt)

            elif action == "edit_attendance":
                from core.state import set_state

                await set_state(
                    pool, "awaiting_uni_input", "university", "edit_attendance", None
                )
                keyboard = InlineKeyboardMarkup([[back_btn]])
                prompt = "✏️ *Editează prezență*\n\nFormat: `Materie, YYYY\\-MM\\-DD, prezent/absent`\nExemplu: `MRU, 2026\\-03\\-23, absent`"
                await query.edit_message_text(
                    prompt,
                    parse_mode="MarkdownV2",
                    reply_markup=keyboard,
                )
                await _save_prompt_to_conversation(pool, prompt)

            elif action == "delete_grade":
                from core.state import set_state

                await set_state(
                    pool, "awaiting_uni_input", "university", "delete_grade", None
                )
                keyboard = InlineKeyboardMarkup([[back_btn]])
                prompt = "🗑 *Șterge notă*\n\nFormat: `Materie, tip`\nExemplu: `Statistică, partial`"
                await query.edit_message_text(
                    prompt,
                    parse_mode="MarkdownV2",
                    reply_markup=keyboard,
                )
                await _save_prompt_to_conversation(pool, prompt)

        # ━━━ ANALIZĂ GEMINI ━━━
        elif section == "analysis":
            from db.queries.university import list_subjects, get_upcoming_exams
            from db.queries.schedule import get_current_week_type
            from datetime import date

            subjects = await list_subjects(pool)
            exams = await get_upcoming_exams(pool, days=60)
            config = await pool.fetchrow(
                "SELECT semester_start FROM semester_config ORDER BY id DESC LIMIT 1"
            )
            week_num = 1
            if config:
                delta = (date.today() - config["semester_start"]).days
                week_num = delta // 7 + 1

            data_ctx = f"""
Săptămâna curentă: {week_num}/14
Materii și situație:
{chr(10).join([f"- {s['name']}: medie {s['avg_grade'] or 'N/A'}, prezențe {s.get('attended_count', 0)}/{s.get('total_seminars', 0)}" for s in subjects])}

Examene upcoming:
{chr(10).join([f"- {e['subject_name']}: {e['exam_date']}" for e in exams]) or "Niciun examen înregistrat"}
"""

            from core.gemini import get_proactive_response

            instruction = """
Ești Lora. Analizează situația academică a lui Robu și oferă o analiză concisă.

Structură:
📊 *Analiză Academică*

*Situație generală:* [1-2 propoziții]
*Riscuri:* [materii cu prezențe scăzute sau fără note]
*Prioritate:* [ce trebuie să facă în săptămânile rămase]

MAX 150 cuvinte. Ton direct, fără laudă.
Dacă nu sunt suficiente date: spune direct.
"""

            result = await get_proactive_response(instruction, data_ctx)

            keyboard = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "🔄 Regenerează",
                            callback_data=make_callback_data("uni", "analysis"),
                        )
                    ],
                    [back_btn],
                ]
            )
            await query.edit_message_text(
                safe_markdown(result)
                if result
                else "Nu sunt suficiente date pentru analiză\\.",
                parse_mode="MarkdownV2",
                reply_markup=keyboard,
            )

        # ━━━ IMPORT ━━━
        elif section == "import":
            if not action:
                keyboard = InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "📸 Import orar din poză",
                                callback_data=make_callback_data(
                                    "uni", "import", "schedule_photo"
                                ),
                            )
                        ],
                        [
                            InlineKeyboardButton(
                                "📄 Structură din PDF",
                                callback_data=make_callback_data(
                                    "uni", "import", "structure_pdf"
                                ),
                            )
                        ],
                        [back_btn],
                    ]
                )
                await query.edit_message_text(
                    "📥 *Import*\n\nAlege ce vrei să importezi:",
                    parse_mode="MarkdownV2",
                    reply_markup=keyboard,
                )

            elif action == "schedule_photo":
                from core.state import set_state

                await set_state(
                    pool,
                    "awaiting_uni_input",
                    "university",
                    "import_schedule_photo",
                    None,
                )
                keyboard = InlineKeyboardMarkup([[back_btn]])
                await query.edit_message_text(
                    "📸 *Import orar din poză*\n\nTrimite o poză cu orarul tău\\.\nLora va extrage automat cursurile și orele\\.",
                    parse_mode="MarkdownV2",
                    reply_markup=keyboard,
                )

            elif action == "structure_pdf":
                from core.state import set_state

                await set_state(
                    pool,
                    "awaiting_uni_input",
                    "university",
                    "import_structure_pdf",
                    None,
                )
                keyboard = InlineKeyboardMarkup([[back_btn]])
                await query.edit_message_text(
                    "📄 *Import structură academică*\n\nTrimite PDF\\-ul cu structura anului universitar\\.\nLora va extrage perioadele \\(activitate didactică, vacanță, sesiune\\)\\.",
                    reply_markup=keyboard,
                )

    except Exception as e:
        print(f"❌ ERROR in handle_uni_callback: {e}")
        traceback.print_exc()
        try:
            await query.message.reply_text(
                safe_markdown(f"A apărut o eroare internă: {str(e)[:100]}"),
                parse_mode="MarkdownV2",
            )
        except Exception:
            pass


async def goals_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != TELEGRAM_USER_ID:
        return
    pool = context.bot_data["pool"]
    try:
        from modules.goals import get_goals_dashboard

        msg, markup = await get_goals_dashboard(pool)
        await update.message.reply_text(
            msg, parse_mode="MarkdownV2", reply_markup=markup
        )
    except Exception as e:
        print(f"Error in goals_command: {e}")
        await update.message.reply_text("❌ Eroare la încărcarea dashboard-ului Goals.")


async def health_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles /health command — opens health dashboard."""
    pool = context.bot_data.get("pool")
    if not await security_check(update):
        return

    from modules.health import handle_health_intent

    text, markup, _ = await handle_health_intent(
        pool, "health_summary", {}, bot=context.bot
    )
    await update.message.reply_text(text, parse_mode="MarkdownV2", reply_markup=markup)


async def finance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles /finance command — opens finance dashboard."""
    pool = context.bot_data.get("pool")
    if not await security_check(update):
        return

    from modules.finance import handle_finance_intent

    text, markup, _ = await handle_finance_intent(pool, "finance_summary", {})
    await update.message.reply_text(text, parse_mode="MarkdownV2", reply_markup=markup)


async def tasks_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles /tasks command — opens tasks dashboard."""
    pool = context.bot_data.get("pool")
    if not await security_check(update):
        return

    from modules.tasks import get_tasks_dashboard

    text, markup = await get_tasks_dashboard(pool)
    await update.message.reply_text(text, parse_mode="MarkdownV2", reply_markup=markup)


async def debug_app_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Debugs the Mini App URL and state."""
    if not await security_check(update):
        return
    url = os.getenv("DASHBOARD_URL", "Not set")
    secret = os.getenv("LORA_API_SECRET", "Not set")

    msg = (
        f"🔍 *Mini App Debug Info*\\:\n\n"
        f"• *URL*\\: `{escape_md(url)}`\n"
        f"• *Secret Length*\\: {len(secret) if secret != 'Not set' else 0}\n"
        f"• *Bot Username*\\: {context.bot.username}\n\n"
        f"If the button doesn't work, ensure the URL is accessible from your phone and ends with `/dashboard/`\\."
    )
    await update.message.reply_text(msg, parse_mode="MarkdownV2")


async def projects_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles /projects command — opens projects dashboard."""
    pool = context.bot_data.get("pool")
    if not await security_check(update):
        return

    from modules.projects import get_projects_dashboard

    text, markup = await get_projects_dashboard(pool)
    await update.message.reply_text(text, parse_mode="MarkdownV2", reply_markup=markup)


async def reading_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles /reading command — opens reading dashboard."""
    pool = context.bot_data.get("pool")
    if not await security_check(update):
        return

    from modules.reading import get_reading_dashboard

    text, markup = await get_reading_dashboard(pool)
    await update.message.reply_text(text, parse_mode="MarkdownV2", reply_markup=markup)

    from core.config import TELEGRAM_USER_ID

    await save_message(pool, TELEGRAM_USER_ID, "assistant", text)


async def memory_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles /memory command — opens memory dashboard."""
    pool = context.bot_data.get("pool")
    if not await security_check(update):
        return

    from modules.memory import handle_memory_intent

    text, markup, _ = await handle_memory_intent(pool, "memory_view", {})
    await update.message.reply_text(text, parse_mode="MarkdownV2", reply_markup=markup)


async def profile_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, pool):
    """Displays the user profile and allows editing."""
    if not await security_check(update):
        return

    from modules.profile import get_user_profile_full
    from bot.formatter import escape_md
    import json

    user_id = update.effective_user.id
    profile = await get_user_profile_full(pool, user_id)

    if not profile:
        await update.message.reply_text("Nu am găsit profilul tău.")
        return

    name = profile.get("name", "Utilizator")
    tone = profile.get("tone", "warm")
    start = profile.get("active_hours_start", "08:00")
    end = profile.get("active_hours_end", "22:00")

    # Format frequent categories if available
    categories_json = profile.get("frequent_categories", "{}")
    if isinstance(categories_json, str):
        categories = json.loads(categories_json)
    else:
        categories = categories_json

    cat_text = ""
    if categories:
        top_cats = sorted(categories.items(), key=lambda x: x[1], reverse=True)[:3]
        cat_text = "\n📊 *Top Categorii:* " + ", ".join(
            [f"`{escape_md(c)}`" for c, _ in top_cats]
        )

    text = (
        f"👤 *Profilul lui {escape_md(name)}*\n\n"
        f"🎭 *Tone:* `{tone}`\n"
        f"⏰ *Ore active:* `{escape_md(str(start)[:5])}` \\- `{escape_md(str(end)[:5])}`\n"
        f"🌍 *Timezone:* `{escape_md(profile.get('timezone', 'UTC'))}`"
        f"{cat_text}\n\n"
        "_Poți edita preferințele folosind butoanele de mai jos:_"
    )

    keyboard = [
        [
            InlineKeyboardButton("🎭 Schimbă Tone", callback_data="profile_edit_tone"),
            InlineKeyboardButton(
                "⏰ Schimbă Orele", callback_data="profile_edit_hours"
            ),
        ],
        [
            InlineKeyboardButton("🔄 Refresh Profile", callback_data="profile_refresh"),
        ],
    ]

    await update.message.reply_text(
        text, parse_mode="MarkdownV2", reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def _save_prompt_to_conversation(pool, prompt: str) -> None:
    """Saves the assistant's prompt to the history table for Gemini context."""
    from db.queries.history import save_message
    from core.config import TELEGRAM_USER_ID

    await save_message(pool, TELEGRAM_USER_ID, "assistant", prompt)


async def handle_eod_callback(query, pool, data):
    """Handles EOD interactive flow callbacks."""
    pass
    pass
    from core.state import set_state, clear_state

    parts = data.split(":")
    action = parts[1]  # mood | tasks
    value = parts[2]  # great/neutral/terrible | all/partial/none

    if action == "mood":
        # Save mood temporarily in state extra
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE conversation_state SET extra = jsonb_set(COALESCE(extra, '{}'), '{eod_mood}', $1) WHERE state_key = 'current'",
                json.dumps(value),
            )

        # Send Question 2
        keyboard = [
            [
                InlineKeyboardButton("✅ Da, toate", callback_data="eod:tasks:all"),
                InlineKeyboardButton("🌗 Parțial", callback_data="eod:tasks:partial"),
                InlineKeyboardButton("❌ Nu", callback_data="eod:tasks:none"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            "Am notat\\! ✍️\\n\n*Ai finalizat task\\-urile planificate pentru azi?*",
            reply_markup=reply_markup,
            parse_mode="MarkdownV2",
        )
        await set_state(pool, "awaiting_eod_tasks", "eod", "tasks", None)

    elif action == "tasks":
        # Get mood from state
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT extra FROM conversation_state WHERE state_key = 'current'"
            )
            extra = row["extra"] if row and row["extra"] else {}
            mood = extra.get("eod_mood", "neutral")

        # Save to DB
        from datetime import date

        today = date.today()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO journal_entries (entry_date, mood, task_completion)
                VALUES ($1, $2, $3)
                ON CONFLICT (entry_date) DO UPDATE SET mood = $2, task_completion = $3, skipped = FALSE
                """,
                today,
                mood,
                value,
            )

            # Mark profile as completed
            from core.config import TELEGRAM_USER_ID

            await conn.execute(
                "UPDATE user_profile SET last_eod_date = $1 WHERE telegram_id = $2",
                today,
                TELEGRAM_USER_ID,
            )

        await clear_state(pool)

        # Generate and send summary
        # Transition to Journal Questions
        questions = (
            "Am notat\\! ✍️\\n\\n"
            "Răspunde la cele 3 întrebări ca să închidem ziua:\\n"
            "*1\\.* Ce a mers bine azi?\\n"
            "*2\\.* Ce ai vrea să faci diferit?\\n"
            "*3\\.* Cum vrei să arate ziua de mâine? \\(tasks, program, priorități\\)\\n\\n"
            "📌 *La ce oră te trezești mâine?* \\(ex: la 7, pe la 8:30\\)"
        )

        await query.edit_message_text(
            questions,
            parse_mode="MarkdownV2",
        )

        from core.state import set_state

        await set_state(pool, "awaiting_evening_response", "journal", "save", None)


async def generate_eod_summary(pool, mood, task_completion):
    """Generates a 2-3 line summary via Gemini based on today's activity."""
    from db.queries.tasks import get_completed_tasks_today
    from db.queries.finance import get_daily_transactions
    from db.queries import workout as workout_queries

    today = date.today()

    # Gather data
    tasks = await get_completed_tasks_today(pool)
    finances = await get_daily_transactions(pool, today)
    workouts = await workout_queries.get_recent_workouts(pool, days=1)

    # Prepare context for Gemini
    context = {
        "mood": mood,
        "task_completion": task_completion,
        "tasks_completed": [t["title"] for t in tasks],
        "expenses": [
            {"amount": f.get("amount"), "category": f.get("category")}
            for f in finances
            if f.get("type") == "expense"
        ],
        "workouts": [w.get("type") for w in workouts],
    }

    from core.gemini import get_proactive_response

    instruction = """Ești Lora. Generezi un sumar EXTREM DE CONCIS (MAXIM 3 rânduri) al zilei utilizatorului.
Include realizările (tasks), mișcarea (sport) și situația financiară scurt.
Ton: cald, empatic, Romglish.
Fără bullet points, doar un text cursiv scurt."""

    summary = await get_proactive_response(
        instruction, json.dumps(context, default=str)
    )
    return summary or "O zi plină și productivă! Odihnă plăcută."


async def send_confirmation_request(
    intent: str,
    data: dict,
    update: Update = None,
    context: ContextTypes.DEFAULT_TYPE = None,
) -> None:
    """Generates a summary of the action and sends the confirmation inline keyboard."""
    summary = generate_action_summary(intent, data)

    from bot.keyboards import action_confirm_keyboard

    reply_markup = action_confirm_keyboard()

    if update and update.message:
        await update.message.reply_text(
            summary, parse_mode="MarkdownV2", reply_markup=reply_markup
        )
    else:
        from core.config import TELEGRAM_USER_ID

        bot = context.bot if context else None
        if bot:
            await bot.send_message(
                chat_id=TELEGRAM_USER_ID,
                text=summary,
                parse_mode="MarkdownV2",
                reply_markup=reply_markup,
            )


def generate_action_summary(intent: str, data: dict) -> str:
    """Generates a user-friendly Romanian action summary, properly escaped for MarkdownV2."""
    from bot.formatter import escape_md

    # Simple Romanian summaries for each write intent
    if intent == "add_task":
        title = escape_md(data.get("title", ""))
        priority = escape_md(data.get("priority", "medium"))
        return f"Ești pe cale să adaugi task\-ul *'{title}'* cu prioritate *'{priority}'*\\. Confirmă?"

    elif intent == "complete_task":
        task_id = escape_md(str(data.get("id") or data.get("task_id") or ""))
        return f"Ești pe cale să finalizezi task\-ul cu ID\-ul *{task_id}*\\. Confirmă?"

    elif intent == "delete_task":
        task_id = escape_md(str(data.get("id") or data.get("task_id") or ""))
        return f"Ești pe cale să ștergi task\-ul cu ID\-ul *{task_id}*\\. Confirmă?"

    elif intent == "edit_task":
        task_id = escape_md(str(data.get("id") or data.get("task_id") or ""))
        return f"Ești pe cale să modifici task\-ul cu ID\-ul *{task_id}*\\. Confirmă?"

    elif intent == "add_project":
        name = escape_md(data.get("name", ""))
        return f"Ești pe cale să creezi proiectul *'{name}'*\\. Confirmă?"

    elif intent == "delete_project":
        proj_id = escape_md(str(data.get("id") or ""))
        return f"Ești pe cale să ștergi proiectul cu ID\-ul *{proj_id}*\\. Confirmă?"

    elif intent == "finance_log":
        t_type = "venit" if data.get("type") == "income" else "cheltuială"
        amount = escape_md(str(data.get("amount", "")))
        cat = escape_md(data.get("category", "altele"))
        return f"Ești pe cale să înregistrezi o *{t_type}* de *{amount} lei* la categoria *'{cat}'*\\. Confirmă?"

    elif intent == "add_category":
        cat = escape_md(data.get("category") or data.get("name") or "")
        return f"Ești pe cale să adaugi categoria financiară *'{cat}'*\\. Confirmă?"

    elif intent == "delete_category":
        cat = escape_md(data.get("category") or data.get("id") or "")
        return f"Ești pe cale să ștergi categoria financiară *'{cat}'*\\. Confirmă?"

    elif intent == "set_budget":
        cat = escape_md(data.get("category", ""))
        amount = escape_md(str(data.get("amount") or data.get("limit") or ""))
        return f"Ești pe cale să setezi bugetul pentru *'{cat}'* la *{amount} lei*\\. Confirmă?"

    elif intent == "log_skill":
        name = escape_md(data.get("name") or data.get("skill") or "")
        dur = escape_md(str(data.get("duration", "")))
        return f"Ești pe cale să înregistrezi progres la skill\-ul *'{name}'* \(*{dur} min*\)\\. Confirmă?"

    elif intent == "add_habit":
        name = escape_md(data.get("name", ""))
        return f"Ești pe cale să adaugi habit\-ul *'{name}'*\\. Confirmă?"

    elif intent == "log_habit":
        name = escape_md(str(data.get("name") or data.get("id") or ""))
        return f"Ești pe cale să bifezi habit\-ul *{name}*\\. Confirmă?"

    elif intent == "delete_habit":
        name = escape_md(str(data.get("name") or data.get("id") or ""))
        return f"Ești pe cale să ștergi habit\-ul *{name}*\\. Confirmă?"

    elif intent == "uni_add_subject":
        name = escape_md(data.get("name", ""))
        return f"Ești pe cale să adaugi materia *'{name}'*\\. Confirmă?"

    elif intent == "uni_log_attendance":
        sub_id = escape_md(str(data.get("subject_id") or ""))
        return f"Ești pe cale să înregistrezi prezența/absența pentru materia cu ID\-ul *{sub_id}*\\. Confirmă?"

    elif intent == "uni_add_grade":
        val = escape_md(str(data.get("grade_value", "")))
        sub_id = escape_md(str(data.get("subject_id") or ""))
        return f"Ești pe cale să adaugi nota *{val}* la materia cu ID\-ul *{sub_id}*\\. Confirmă?"

    elif intent == "uni_add_exam":
        sub_id = escape_md(str(data.get("subject_id") or ""))
        dt = escape_md(str(data.get("exam_date") or ""))
        return f"Ești pe cale să adaugi examenul la materia cu ID\-ul *{sub_id}* pe data de *{dt}*\\. Confirmă?"

    elif intent == "health_log":
        sleep = escape_md(str(data.get("sleep_hours") or ""))
        water = escape_md(str(data.get("water_ml") or ""))
        cigarettes = escape_md(str(data.get("cigarettes") or ""))
        parts = []
        if sleep:
            parts.append(f"*{sleep} ore de somn*")
        if water:
            parts.append(f"*{water} ml apă*")
        if cigarettes:
            parts.append(f"*{cigarettes} țigări*")
        parts_str = ", ".join(parts)
        return f"Ești pe cale să înregistrezi în log\-ul de sănătate: {parts_str}\\. Confirmă?"

    elif intent == "log_water":
        amount = escape_md(str(data.get("amount") or data.get("water_ml") or ""))
        return f"Ești pe cale să înregistrezi *{amount} ml* de apă\\. Confirmă?"

    elif intent == "workout_log":
        sport = escape_md(data.get("sport") or data.get("workout_type") or "")
        return f"Ești pe cale să înregistrezi antrenamentul de *'{sport}'*\\. Confirmă?"

    elif intent == "workout_add_sport":
        name = escape_md(data.get("name", ""))
        return f"Ești pe cale să adaugi sportul *'{name}'*\\. Confirmă?"

    elif intent == "workout_add_exercise":
        name = escape_md(data.get("name", ""))
        return f"Ești pe cale să adaugi exercițiul *'{name}'*\\. Confirmă?"

    elif intent == "add_note":
        title = escape_md(data.get("title", ""))
        return f"Ești pe cale să adaugi o notă *'{title}'*\\. Confirmă?"

    elif intent == "add_event":
        title = escape_md(data.get("title", ""))
        return f"Ești pe cale să adaugi evenimentul *'{title}'*\\. Confirmă?"

    elif intent == "add_shopping_item":
        item = escape_md(data.get("item") or data.get("name") or "")
        return f"Ești pe cale să adaugi *'{item}'* pe lista de cumpărături\\. Confirmă?"

    elif intent == "add_goal":
        title = escape_md(data.get("title", ""))
        return f"Ești pe cale să adaugi obiectivul *'{title}'*\\. Confirmă?"

    else:
        return f"Ești pe cale să efectuezi acțiunea de tip *'{escape_md(intent)}'*\\. Confirmă?"
