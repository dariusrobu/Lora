# modules/workout.py

from typing import Any, Tuple
import db.queries.workout as workout_queries
from bot.formatter import escape_md
from datetime import date

async def handle_workout_intent(pool, intent: str, data: dict, bot=None):
    import db.queries.sport_types as sport_queries
    from bot.keyboards import workout_main_keyboard
    
    if intent == "workout_log":
        date_str = data.get("date")
        if date_str:
            try:
                workout_date = date.fromisoformat(date_str)
            except ValueError:
                workout_date = date.today()
        else:
            workout_date = date.today()
            
        sport_name = data.get("sport_name", "Gym")
        duration = data.get("duration_min", 0)
        notes = data.get("notes") or ""
        exercises = data.get("exercises", [])
        
        sports = await sport_queries.get_all_sports(pool)
        matched_sport = next((s for s in sports if s['name'].lower() == sport_name.lower()), None)
        
        if matched_sport:
            sport_id = matched_sport['id']
            icon = matched_sport.get('icon', '')
        else:
            try:
                await sport_queries.add_sport(pool, sport_name, "Sport", False, True, True, "🏃")
                sports = await sport_queries.get_all_sports(pool)
                sport_id = next((s['id'] for s in sports if s['name'].lower() == sport_name.lower()), 1)
                icon = "🏃"
            except Exception:
                sport_id = sports[0]['id'] if sports else 1
                icon = "��"
        
        workout_id = await workout_queries.log_workout(
            pool, workout_date, sport_id, duration, notes
        )
        
        ex_summary = []
        for ex in exercises:
            name = ex.get("name", "")
            if name:
                await workout_queries.log_exercise(
                    pool, workout_id, name,
                    ex.get("sets"), ex.get("reps"), ex.get("weight_kg")
                )
                str_ex = f"{name}"
                if ex.get("weight_kg"):
                    str_ex += f" {ex.get('weight_kg')}kg"
                ex_summary.append(str_ex)
        
        reply = f"✅ Antrenament salvat: {icon} *{escape_md(sport_name)}* \({duration} min\)\."
        if ex_summary:
            reply += "\n" + escape_md(", ".join(ex_summary))
            
        return reply, workout_main_keyboard()

    elif intent == "workout_list":
        return await get_workout_dashboard(pool)
        
    elif intent == "workout_week":
        return await get_week_summary(pool)
        
    elif intent == "workout_stats":
        days = data.get("period_days", 30)
        return await get_stats(pool, days)
        
    elif intent == "workout_prs":
        return await get_personal_records(pool)
        
    elif intent == "workout_add_sport":
        name = data.get("name")
        cat = data.get("category", "Sport")
        if name:
            await sport_queries.add_sport(pool, name, cat, False, True, True, "🏅")
            return f"✅ Sportul *{escape_md(name)}* a fost adăugat\\.", workout_main_keyboard()
            
    elif intent == "workout_add_exercise":
        name = data.get("name")
        cat = data.get("category", "Forță")
        muscle = data.get("muscle_group", "Full Body")
        if name:
            await workout_queries.add_exercise(pool, name, cat, muscle)
            return f"✅ Exercițiul *{escape_md(name)}* a fost adăugat\\.", workout_main_keyboard()

    return "Nu am înțeles cererea legată de antrenamente.", None

# ── Workout Dashboard UI Functions ─────────────────────────────

from bot.keyboards import (
    workout_main_keyboard, workout_stats_period_keyboard,
    sports_list_keyboard, exercises_list_keyboard
)
import db.queries.sport_types as sport_queries

async def get_workout_dashboard(pool) -> Tuple[str, Any]:
    stats = await workout_queries.get_week_stats(pool)
    lines = [
        "🏋️‍♂️ *Workout Dashboard* 🏋️‍♂️\n",
        f"📅 Sesiuni săptămâna asta: *{stats['sessions']}*",
        f"⏱️ Volum total: *{stats['total_min']} min*",
        f"🔥 Zile active: *{stats['active_days']}/7*\n"
    ]
    
    if stats.get('split'):
        lines.append("📊 *Split sporturi:*")
        for sp in stats['split']:
            lines.append(f"• {sp.get('icon', '')} {escape_md(sp['name'])}: {sp['sessions']}x")
            
    recent = await workout_queries.get_recent_workouts(pool, days=3)
    if recent:
        lines.append("\n🕐 *Ultimul antrenament:*")
        last = recent[0]
        date_str = escape_md(str(last['workout_date']))
        type_str = escape_md(last['type'])
        lines.append(f"{last.get('icon', '')} *{type_str}* pe {date_str} \\({last['duration_min']}m\\)")
        
    return "\n".join(lines), workout_main_keyboard()

async def get_week_summary(pool) -> Tuple[str, Any]:
    stats = await workout_queries.get_week_stats(pool)
    lines = [
        "📅 *Săptămâna Curentă*\n",
        f"Antrenamente: *{stats['sessions']}*",
        f"Timp total: *{stats['total_min']} min*",
        f"Zile bifate: *{stats['active_days']} / 7*\n"
    ]
    if stats.get('split'):
        lines.append("📈 *Repartiție*")
        for sp in stats['split']:
            lines.append(f"• {sp.get('icon', '')} {escape_md(sp['name'])}: {sp['sessions']} sesiuni")
    else:
        lines.append("Niciun antrenament înregistrat săptămâna asta\\.")
        
    return "\n".join(lines), None

async def get_personal_records(pool) -> Tuple[str, Any]:
    prs = await workout_queries.get_personal_records(pool)
    if not prs:
        return "🏆 *Personal Records*\n\nÎncă nu ai înregistrat greutăți la exerciții\\.", None
        
    lines = ["🏆 *Personal Records*\n"]
    for pr in prs:
        lines.append(f"• {escape_md(pr['exercise_name'])}: *{pr['max_weight']}kg*")
        
    return "\n".join(lines), None

async def get_stats(pool, period_days: int) -> Tuple[str, Any]:
    stats = await workout_queries.get_long_term_stats(pool, days=period_days)
    if not stats or not stats.get('total_sessions'):
        return f"📊 *Statistici \\({period_days} zile\\)*\n\nFără date suficiente\\.", workout_stats_period_keyboard()
        
    lines = [
        f"📊 *Statistici \\({period_days} zile\\)*\n",
        f"• Sesiuni: *{stats['total_sessions']}*",
        f"• Zile active: *{stats['active_days']}*",
        f"• Timp: *{stats['total_min']} min*",
        f"• Media/sesiune: *{stats['avg_duration'] or 0} min*",
        f"• Sport preferat: *{escape_md(stats['most_common_type'] or '-')}*\n",
    ]
    
    if stats.get('by_type'):
        lines.append("🏋️ *Top sporturi*")
        for t in stats['by_type'][:3]:
            lines.append(f"• {t.get('icon', '')} {escape_md(t['type'])}: {t['count']}x \\({t['total_min']}m\\)")
            
    return "\n".join(lines), workout_stats_period_keyboard()

async def get_sports_manager(pool) -> Tuple[str, Any]:
    sports = await sport_queries.get_all_sports(pool)
    msg = "⚙️ *Management Sporturi*\n\nAlege un sport pentru a\\-l edita/șterge, sau adaugă unul nou\\."
    return msg, sports_list_keyboard(sports)

async def get_exercises_manager(pool) -> Tuple[str, Any]:
    exercises = await workout_queries.get_all_exercises(pool)
    msg = "🏋️ *Management Exerciții*\n\nAlege un exercițiu pentru a\\-l edita/șterge, sau adaugă unul nou\\."
    return msg, exercises_list_keyboard(exercises)

# ── Telegram Handlers Integration ──────────────────────────────

from core.state import set_state, clear_state
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
import traceback

async def handle_workout_callback(query, pool, data: str):
    await query.answer()
    parts = data.split("_")
    action = "_".join(parts[1:3]) if len(parts) >= 3 else parts[1] if len(parts) >= 2 else ""

    if data == "workout_main":
        text, markup = await get_workout_dashboard(pool)
        await query.edit_message_text(text, parse_mode="MarkdownV2", reply_markup=markup)
        
    elif data == "workout_log":
        sports = await sport_queries.get_all_sports(pool)
        keyboard = []
        for i in range(0, len(sports), 2):
            row = [InlineKeyboardButton(f"{sports[i].get('icon', '')} {sports[i]['name']}", callback_data=f"workout_log_sport_{sports[i]['id']}")]
            if i + 1 < len(sports):
                row.append(InlineKeyboardButton(f"{sports[i+1].get('icon', '')} {sports[i+1]['name']}", callback_data=f"workout_log_sport_{sports[i+1]['id']}"))
            keyboard.append(row)
        keyboard.append([InlineKeyboardButton("⬅️ Înapoi", callback_data="workout_main")])
        await query.edit_message_text("📝 *Log Antrenament*\n\nAlege sportul:", parse_mode="MarkdownV2", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("workout_log_sport_"):
        sport_id = int(parts[-1])
        await set_state(pool, "awaiting_workout_input", "workout", "log_duration", sport_id)
        await query.edit_message_text("⏱ Câte minute a durat antrenamentul?\n_Scrie doar numărul_.", parse_mode="MarkdownV2", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Anulează", callback_data="workout_main")]]))

    elif data == "workout_stats_menu":
        await query.edit_message_text("📊 Alege perioada pentru statistici:", reply_markup=workout_stats_period_keyboard())

    elif data.startswith("workout_stats_") and parts[-1].isdigit():
        days = int(parts[-1])
        text, markup = await get_stats(pool, days)
        await query.edit_message_text(text, parse_mode="MarkdownV2", reply_markup=markup)

    elif data == "workout_prs":
        text, markup = await get_personal_records(pool)
        await query.edit_message_text(text, parse_mode="MarkdownV2", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Înapoi", callback_data="workout_main")]]))

    elif data == "workout_week":
        text, markup = await get_week_summary(pool)
        await query.edit_message_text(text, parse_mode="MarkdownV2", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Înapoi", callback_data="workout_main")]]))

    elif data == "workout_sports":
        text, markup = await get_sports_manager(pool)
        await query.edit_message_text(text, parse_mode="MarkdownV2", reply_markup=markup)

    elif data == "workout_exercises":
        text, markup = await get_exercises_manager(pool)
        await query.edit_message_text(text, parse_mode="MarkdownV2", reply_markup=markup)

    elif data == "workout_add_sport":
        await set_state(pool, "awaiting_workout_input", "workout", "add_sport", None)
        await query.edit_message_text("➕ *Adaugă sport*\n\nScrie în format: `Nume, Categorie, distance/weight/reps, icon`\n_Categorii: Forță / Cardio / Sport / Mobilitate_", parse_mode="MarkdownV2", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Anulează", callback_data="workout_main")]]))

    elif data == "workout_add_exercise":
        await set_state(pool, "awaiting_workout_input", "workout", "add_exercise", None)
        await query.edit_message_text("➕ *Adaugă exercițiu*\n\nScrie în format: `Nume, Categorie, Grupa Musculară`", parse_mode="MarkdownV2", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Anulează", callback_data="workout_main")]]))

    elif action == "delete_sport":
        sport_id = int(parts[-1])
        success = await sport_queries.delete_sport(pool, sport_id)
        if success:
            await query.answer("Sport șters!")
        else:
            await query.answer("Nu se poate șterge — are antrenamente asociate!", show_alert=True)
        text, markup = await get_sports_manager(pool)
        await query.edit_message_text(text, parse_mode="MarkdownV2", reply_markup=markup)

    elif action == "delete_exercise":
        ex_id = int(parts[-1])
        await workout_queries.delete_exercise(pool, ex_id)
        await query.answer("Exercițiu șters!")
        text, markup = await get_exercises_manager(pool)
        await query.edit_message_text(text, parse_mode="MarkdownV2", reply_markup=markup)

    elif data == "workout_delete":
        recent = await workout_queries.get_recent_workouts(pool, days=30)
        keyboard = []
        for w in recent[:10]:
            label = f"{w['workout_date']} - {w['type']} ({w['duration_min']}m)"
            keyboard.append([InlineKeyboardButton(label, callback_data=f"w_del_{w['id']}")])
        keyboard.append([InlineKeyboardButton("⬅️ Înapoi", callback_data="workout_main")])
        await query.edit_message_text("🗑 *Șterge antrenament*\n\nAlege antrenamentul:", parse_mode="MarkdownV2", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("w_del_"):
        try:
            workout_id = int(parts[-1])
            await workout_queries.delete_workout(pool, workout_id)
            await query.answer("Antrenament șters!")
            text, markup = await get_workout_dashboard(pool)
            await query.edit_message_text(text, parse_mode="MarkdownV2", reply_markup=markup)
        except Exception:
            await query.answer("Eroare la ștergere.")

    elif data == "workout_edit":
        await query.answer("Folosește Gemini vocal ('editează antrenamentul de ieri') pentru editări complexe.", show_alert=True)

async def handle_workout_message(update, pool, state: dict, text: str):
    action = state.get("action")
    item_id = state.get("item_id")

    try:
        if action == "add_sport":
            parts = [p.strip() for p in text.split(',')]
            name = parts[0]
            category = parts[1] if len(parts) > 1 else "Sport"
            flags = parts[2].lower() if len(parts) > 2 else ""
            has_dist = "distance" in flags
            has_wt = "weight" in flags
            has_reps = "reps" in flags
            icon = parts[3] if len(parts) > 3 else "🏅"
            await sport_queries.add_sport(pool, name, category, has_dist, has_wt, has_reps, icon)
            await update.message.reply_text(f"✅ Sportul *{escape_md(name)}* a fost adăugat\\.", parse_mode="MarkdownV2")
            
        elif action == "add_exercise":
            parts = [p.strip() for p in text.split(',')]
            name = parts[0]
            category = parts[1] if len(parts) > 1 else "Forță"
            muscle = parts[2] if len(parts) > 2 else "Full Body"
            await workout_queries.add_exercise(pool, name, category, muscle)
            await update.message.reply_text(f"✅ Exercițiul *{escape_md(name)}* a fost adăugat\\.", parse_mode="MarkdownV2")
            
        elif action == "log_duration":
            duration = int(text.strip())
            from datetime import date
            workout_id = await workout_queries.log_workout(pool, date.today(), item_id, duration, "")
            await update.message.reply_text(f"✅ Antrenament salvat: {duration} min\\. Poți folosi integrarea vocală pentru detalii extra\\.", parse_mode="MarkdownV2")
            
    except Exception as e:
        print(f"Error in workout state handler: {e}")
        traceback.print_exc()
        await update.message.reply_text(f"❌ Format incorect: {e}")
        
    finally:
        await clear_state(pool)
