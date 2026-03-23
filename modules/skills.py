from typing import Dict, Any, Tuple, Optional
from telegram import InlineKeyboardMarkup
from bot.formatter import escape_md
import db.queries.skills as skill_queries
from bot.keyboards import (
    skills_main_keyboard, 
    skills_list_keyboard, 
    skill_detail_keyboard,
    confirm_delete_skill_keyboard
)

async def get_skills_dashboard(pool) -> Tuple[str, InlineKeyboardMarkup]:
    """Renders the main skills overview."""
    skills = await skill_queries.get_all_skills(pool)
    
    if not skills:
        return "🧠 *Skills Tracking*\n\nNu ai skill-uri adăugate încă. Folosește butonul de mai jos pentru a începe!", skills_list_keyboard([])
        
    lines = ["🧠 *Skills Tracking*\n"]
    for s in skills:
        val = s.get('last_value')
        unit = s.get('unit', '')
        if val is not None:
            # Format value: 1200 or 1:20 if it looks like seconds? 
            # For now, keep it simple.
            val_str = f"{float(val):.0f}" if float(val) == int(val) else f"{float(val):.2f}"
            lines.append(f"• *{escape_md(s['name'])}*: {val_str} {escape_md(unit)}")
        else:
            lines.append(f"• *{escape_md(s['name'])}*: _fără date_")
            
    return "\n".join(lines), skills_main_keyboard()

async def get_skill_detail_view(pool, skill_id: int) -> Tuple[str, InlineKeyboardMarkup]:
    skill = await skill_queries.get_skill_by_id(pool, skill_id)
    if not skill:
        return "❌ Skill-ul nu mai există\\.", skills_main_keyboard()
        
    stats = await skill_queries.get_skill_stats(pool, skill_id)
    history = await skill_queries.get_skill_history(pool, skill_id, limit=5)
    
    title = escape_md(skill['name'])
    unit = escape_md(skill['unit'])
    
    lines = [
        f"📊 *{title}* ({escape_md(skill['category'])})\n",
        f"• *Medie*: {stats['avg']:.2f} {unit}",
        f"• *Best/Max*: {stats['max']:.2f} {unit}",
        f"• *Trend*: {'📈' if stats['trend'] > 0 else '📉' if stats['trend'] < 0 else '➡️'} {abs(stats['trend']):.2f} {unit}\n",
        "*Istoric Recent:*"
    ]
    
    for h in history:
        date_str = h['log_date'].strftime('%d %b')
        val_str = f"{float(h['value']):.0f}" if float(h['value']) == int(h['value']) else f"{float(h['value']):.2f}"
        lines.append(f"• {date_str}: {val_str} {unit}")
        
    if not history:
        lines.append("_Nicio înregistrare încă_")
        
    return "\n".join(lines), skill_detail_keyboard(skill_id)

async def handle_skill_intent(pool, intent: str, data: Dict[str, Any]) -> Tuple[str, Optional[InlineKeyboardMarkup]]:
    """NLP Entry point from Gemini."""
    if intent == "log_skill":
        name = data.get("skill_name")
        value = data.get("value")
        # Try to find skill
        skill = await skill_queries.get_skill_by_name(pool, name)
        if not skill:
            # Auto-create? No, better ask to create first or handle in state
            return f"❌ Nu am găsit skill-ul '{escape_md(name)}\\'\\. Vrei să îl creez?", None # TODO: Suggest creation
            
        await skill_queries.log_skill_value(pool, skill['id'], float(value))
        return f"✅ Am înregistrat {value} {escape_md(skill['unit'])} pentru *{escape_md(skill['name'])}*!", None
        
    elif intent == "view_skills":
        return await get_skills_dashboard(pool)
        
    return "Intent necunoscut pentru Skills\\.", None

async def handle_skills_callback(update, context, pool) -> None:
    """Router for skills_ callbacks."""
    query = update.callback_query
    data = query.data
    from core.state import set_state, clear_state
    
    try:
        if data == "skills_list":
            text, markup = await get_skills_dashboard(pool)
            await query.edit_message_text(text, reply_markup=markup, parse_mode="MarkdownV2")
            
        elif data.startswith("skills_detail_"):
            skill_id = int(data.split("_")[-1])
            text, markup = await get_skill_detail_view(pool, skill_id)
            await query.edit_message_text(text, reply_markup=markup, parse_mode="MarkdownV2")
            
        elif data == "skills_add_new":
            await set_state(pool, "skills_add_name")
            await query.edit_message_text("➕ *Skill Nou*\n\nIntrodu numele skill-ului (ex: Sah, Duolingo, Rubik):", parse_mode="MarkdownV2")
            
        elif data.startswith("skills_log_entry_"):
            skill_id = int(data.split("_")[-1])
            skill = await skill_queries.get_skill_by_id(pool, skill_id)
            await set_state(pool, f"skills_log_value_{skill_id}")
            await query.edit_message_text(f"📝 *Log {escape_md(skill['name'])}*\n\nIntrodu valoarea ({escape_md(skill['unit'])}):", parse_mode="MarkdownV2")
            
        elif data.startswith("skills_delete_"):
            skill_id = int(data.split("_")[-1])
            await query.edit_message_text("⚠️ Sigur vrei să ștergi acest skill și tot istoricul său?", reply_markup=confirm_delete_skill_keyboard(skill_id))
            
        elif data.startswith("skills_confirm_delete_"):
            skill_id = int(data.split("_")[-1])
            await skill_queries.delete_skill(pool, skill_id)
            await query.answer("Skill șters!")
            text, markup = await get_skills_dashboard(pool)
            await query.edit_message_text(text, reply_markup=markup, parse_mode="MarkdownV2")
            
        elif data == "skills_cancel":
            await clear_state(pool)
            text, markup = await get_skills_dashboard(pool)
            await query.edit_message_text(text, reply_markup=markup, parse_mode="MarkdownV2")
            
        await query.answer()
    except Exception as e:
        import logging
        logging.error(f"Error in skills callback: {e}")
        await query.answer("Eroare la procesarea cererii\\.")

async def handle_skills_message(update, context, pool, state: str) -> bool:
    """Handles text input for skills state machine."""
    from core.state import set_state, clear_state
    msg_text = update.message.text.strip()
    
    try:
        if state == "skills_add_name":
            await set_state(pool, "skills_add_unit", metadata={"name": msg_text})
            await update.message.reply_text(f"✅ Nume: *{escape_md(msg_text)}*\n\nAcum introdu unitatea de măsură (ex: elo, min, kg, puncte):", parse_mode="MarkdownV2")
            return True
            
        elif state == "skills_add_unit":
            from core.state import get_state
            current_state = await get_state(pool)
            name = current_state['metadata'].get("name")
            unit = msg_text
            await skill_queries.add_skill(pool, name, unit=unit)
            await clear_state(pool)
            text, markup = await get_skills_dashboard(pool)
            await update.message.reply_text(f"🎉 Skill-ul *{escape_md(name)}* a fost adăugat!", parse_mode="MarkdownV2")
            await update.message.reply_text(text, reply_markup=markup, parse_mode="MarkdownV2")
            return True
            
        elif state.startswith("skills_log_value_"):
            skill_id = int(state.split("_")[-1])
            try:
                # Remove unit if user included it (e.g. "1200 elo" -> 1200)
                val_raw = msg_text.split()[0].replace(",", ".")
                val = float(val_raw)
            except ValueError:
                await update.message.reply_text("❌ Te rog introdu un număr valid\\.")
                return True
                
            await skill_queries.log_skill_value(pool, skill_id, val)
            await clear_state(pool)
            text, markup = await get_skill_detail_view(pool, skill_id)
            await update.message.reply_text("✅ Valoare înregistrată!", parse_mode="MarkdownV2")
            await update.message.reply_text(text, reply_markup=markup, parse_mode="MarkdownV2")
            return True
            
    except Exception as e:
        import logging
        logging.error(f"Error in skills message: {e}")
        await update.message.reply_text("❌ A apărut o eroare la salvarea datelor\\.")
        await clear_state(pool)
        return True
        
    return False

async def skills_command(update, context) -> None:
    """/skills command handler."""
    pool = context.bot_data["pool"]
    try:
        text, markup = await get_skills_dashboard(pool)
        await update.message.reply_text(text, reply_markup=markup, parse_mode="MarkdownV2")
    except Exception as e:
        import logging
        logging.error(f"Error in skills command: {e}")
        await update.message.reply_text("Eroare la deschiderea dashboard-ului de skills\\.")
