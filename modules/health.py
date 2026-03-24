from typing import Dict, Any, Tuple
from datetime import date
import io
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from bot.formatter import escape_md
import db.queries.health as health_queries

async def handle_health_intent(pool, intent: str, data: Dict[str, Any], bot=None) -> Tuple[str, Any]:
    """
    Main router for health-related intents.
    """
    today = date.today()
    
    if intent in ["health_log", "log_health", "log_sleep", "log_weight", "log_nutrition", "nutrition_log"]:

        return await _handle_upsert(pool, intent, data, today)
    
    elif intent == "log_water":
        water_ml = data.get("water_ml")
        if not water_ml:
            return "Câți ml ai băut? 💧", None
        
        new_total = await health_queries.add_water(pool, today, water_ml)
        return escape_md(f"✅ +{water_ml}ml adăugați. Total azi: {new_total}ml. 💧"), None
    
    elif intent == "health_summary":
        return await _generate_health_summary_text(pool)
    
    elif intent == "health_chart":
        return await _generate_health_chart(pool)
    
    elif intent == "view_today_logs":
        return await _generate_today_logs_text(pool)
    
    return escape_md("Nu sunt sigură cum să procesez această cerere pentru sănătate. 🤔"), None


async def _handle_upsert(pool, intent: str, data: Dict[str, Any], log_date: date) -> Tuple[str, Any]:
    sleep_hours = data.get("sleep_hours")
    sleep_quality = data.get("sleep_quality")
    water_ml = data.get("water_ml")
    nutrition = data.get("nutrition")
    weight_kg = data.get("weight_kg")
    notes = data.get("notes")
    
    await health_queries.upsert_health_log(
        pool, log_date, 
        sleep_hours=sleep_hours, 
        sleep_quality=sleep_quality,
        water_ml=water_ml,
        nutrition=nutrition,
        weight_kg=weight_kg,
        notes=notes
    )
    
    # Build a nice confirmation message
    parts = []
    if sleep_hours is not None:
        parts.append(f"somn {sleep_hours}h ✓")
    if water_ml is not None:
        parts.append(f"apă {water_ml}ml ✓")
    if weight_kg is not None:
        parts.append(f"{weight_kg}kg ✓")
    if nutrition is not None:
        parts.append(f"nutriție: {nutrition} ✓")
    
    if not parts:
        return "Am salvat log-ul de sănătate. ✅", None
    
    msg = "✅ Health logat — " + "  ".join(parts)
    return escape_md(msg), None

async def _generate_health_summary_text(pool) -> Tuple[str, Any]:
    import db.queries.nutrition as nutrition_queries
    
    summary = await health_queries.get_health_summary(pool, 7)
    nutrition_today = await nutrition_queries.get_daily_totals(pool, date.today())
    targets = await nutrition_queries.get_nutrition_targets(pool)
    
    if not summary or summary.get('total_days', 0) == 0:
        return "Nu am destule date pentru un rezumat încă. Mai loghează câteva zile! 📊", None
    
    avg_sleep = summary.get('avg_sleep', 0) or 0
    common_quality = summary.get('common_sleep_quality', '—')
    avg_water = summary.get('avg_water', 0) or 0
    max_water = summary.get('max_water', 0) or 0
    recent_weight = summary.get('recent_weight', '—')
    trend_emoji = "↓" if summary.get('weight_trend') == "down" else "↑" if summary.get('weight_trend') == "up" else "→"
    
    # Nutrition part
    nutri_text = "Nicio masă azi."
    if nutrition_today['calories'] > 0:
        cal_pct = min(int((nutrition_today['calories'] / targets['calories']) * 100), 100)
        nutri_text = f"{int(nutrition_today['calories'])}/{targets['calories']} kcal ({cal_pct}%) · {int(nutrition_today['protein'])}g P"
    
    text = (
        "📊 *Health — ultimele 7 zile*\n\n"
        f"😴 *Somn:* medie {avg_sleep:.1f}h · {common_quality}\n"
        f"💧 *Apă:* medie {int(avg_water)}ml · max {max_water}ml\n"
        f"⚖️ *Greutate:* {recent_weight}kg (trend: {trend_emoji})\n"
        f"🍎 *Nutriție Azi:* {nutri_text}"
    )
    
    from bot.formatter import safe_markdown
    text = safe_markdown(text)
    
    # Inline buttons for /health
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💧 Apă", callback_data="health_log_water"),
            InlineKeyboardButton("😴 Somn", callback_data="health_log_sleep")
        ],
        [
            InlineKeyboardButton("⚖️ Greutate", callback_data="health_log_weight"),
            InlineKeyboardButton("🍎 Nutriție", callback_data="health_log_nutrition")
        ],
        [InlineKeyboardButton("📊 Grafic COMPLET", callback_data="health_chart")],
        [InlineKeyboardButton("📜 Jurnal AZI", callback_data="health_today_logs")]
    ])
    
    return text, keyboard


async def _generate_health_chart(pool) -> Tuple[str, Any]:
    history = await health_queries.get_health_history(pool, 30)
    if len(history) < 3:
        return "Am nevoie de măcar 3 zile logate pentru a genera un grafic relevant. 📉", None
    
    dates = [row['log_date'] for row in history]
    sleep_vals = [float(row['sleep_hours']) if row['sleep_hours'] else None for row in history]
    water_vals = [row['water_ml'] if row['water_ml'] else 0 for row in history]
    weight_vals = [float(row['weight_kg']) if row['weight_kg'] else None for row in history]
    
    # Handle None values for plotting lines by interpolation or skipping
    # Matplotlib handles None as gaps, which is fine.
    
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(10, 15), sharex=True)
    plt.subplots_adjust(hspace=0.3)
    
    # 1. Sleep
    ax1.plot(dates, sleep_vals, color='#3498db', marker='o', linewidth=2, label='Somn (h)')
    ax1.set_title('Somn (ore)', fontsize=14, pad=10)
    ax1.grid(True, alpha=0.3)
    ax1.set_ylabel('Ore')
    
    # 2. Water
    ax2.bar(dates, water_vals, color='#2ecc71', alpha=0.7, label='Apă (ml)')
    ax2.set_title('Apă (ml)', fontsize=14, pad=10)
    ax2.grid(True, alpha=0.3)
    ax2.set_ylabel('ml')
    
    # 3. Weight
    # Remove Nones from weight to avoid gaps in line
    weight_dates = [d for d, w in zip(dates, weight_vals) if w is not None]
    weight_clean = [w for w in weight_vals if w is not None]
    if weight_clean:
        ax3.plot(weight_dates, weight_clean, color='#e67e22', marker='s', linewidth=2, label='Greutate (kg)')
        ax3.set_title('Greutate (kg)', fontsize=14, pad=10)
        ax3.grid(True, alpha=0.3)
        ax3.set_ylabel('kg')
    
    # Formatting X axis
    ax3.xaxis.set_major_formatter(mdates.DateFormatter('%d %b'))
    plt.xticks(rotation=45)
    
    # Save to buffer
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=100)
    buf.seek(0)
    plt.close(fig)
    
    
    return buf, "photo"

async def _generate_today_logs_text(pool) -> Tuple[str, Any]:
    """Generates a detailed summary of all logs for today."""
    import db.queries.nutrition as nutrition_queries
    from bot.formatter import safe_markdown
    
    today = date.today()
    health = await health_queries.get_health_log(pool, today)
    meals = await nutrition_queries.get_daily_meals(pool, today)
    totals = await nutrition_queries.get_daily_totals(pool, today)
    
    if not health and not meals:
        return "Nu ai logat nimic pentru azi încă. 🍎💧", None
    
    # Header
    text = f"📜 *Jurnal Sănătate — {today.strftime('%d %b %Y')}*\n\n"
    
    # 1. Health Metrics
    if health:
        metrics = []
        if health.get('sleep_hours'): metrics.append(f"😴 *Somn:* {health['sleep_hours']}h ({health.get('sleep_quality', '—')})")
        if health.get('water_ml'): metrics.append(f"💧 *Apă:* {health['water_ml']}ml")
        if health.get('weight_kg'): metrics.append(f"⚖️ *Greutate:* {health['weight_kg']}kg")
        if health.get('notes'): metrics.append(f"📝 *Note:* {health['notes']}")
        
        if metrics:
            text += "\n".join(metrics) + "\n\n"
    
    # 2. Meals
    if meals:
        text += "🍎 *Mese:* \n"
        for i, m in enumerate(meals, 1):
            time_str = m['created_at'].strftime('%H:%M')
            text += f"{i}. `[{time_str}]` *{m['total_calories']} kcal* — {m['description']}\n"
        
        # Totals
        text += f"\n🔥 *Total Calorii:* {int(totals['calories'])} kcal\n"
        text += f"📊 *Macros:* {int(totals['protein'])}g P · {int(totals['carbs'])}g C · {int(totals['fat'])}g F\n"
    else:
        text += "🍎 *Mese:* Nicio masă logată încă.\n"
    
    text = safe_markdown(text)
    
    # Button to go back to summary
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Înapoi la Dashboard", callback_data="health_summary")]])
    
    return text, keyboard
