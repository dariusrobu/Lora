from typing import Dict, Any, Tuple
from datetime import datetime, date, timedelta
import db.queries.habits as habit_queries
from bot.formatter import escape_md
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import io

async def handle_habit_intent(pool, intent: str, data: Dict[str, Any], bot=None) -> Tuple[str | None, Any]:
    """Handles habit-related intents and returns reply text + keyboard."""
    
    if intent == "add_habit":
        name = data.get("name") or data.get("title") or data.get("description")
        if not name:
            return "What habit should I add?", None
            
        habit_id = await habit_queries.add_habit(
            pool, 
            name=name,
            frequency=data.get("frequency", "daily"),
            target_days=data.get("target_days")
        )
        
        from bot.keyboards import habit_keyboard
        return f"Got it ✅ Added *{escape_md(name)}* to your habits\\.", habit_keyboard(habit_id)

    elif intent == "list_habits":
        habits = await habit_queries.list_habits(pool)
        if not habits:
            return "You haven't set up any habits yet\\.", None
            
        today_logged = await habit_queries.get_today_logs(pool)
        
        lines = ["✅ *Status Habit-uri Azi:*"]
        for h in habits:
            status = "✅" if h['id'] in today_logged else "⬜"
            streak = f" — Streak: *{h['streak_count']}* 🔥" if h['streak_count'] > 0 else ""
            lines.append(f"{status} *{escape_md(h['name'])}*{streak}")
            
        from bot.keyboards import habit_list_keyboard
        return "\n".join(lines), habit_list_keyboard(habits)

    elif intent == "log_habit":
        habit_id = data.get("id")
        search_name = str(data.get("name") or data.get("title") or data.get("query") or "")
        
        if not habit_id and search_name:
            if search_name.isdigit():
                habit_id = int(search_name)
            else:
                matches = await habit_queries.get_habits_by_name(pool, search_name)
                if len(matches) == 1:
                    habit_id = matches[0]['id']
                elif len(matches) > 1:
                    from bot.keyboards import habit_list_keyboard
                    return f"I found multiple habits named *{escape_md(search_name)}*. Which one are we logging?", habit_list_keyboard(matches)

        if not habit_id:
            # Maybe the user sent the name, but Gemini should resolve to ID
            return "Which habit are we logging?", None
            
        await habit_queries.log_habit(pool, habit_id, datetime.now().date(), "done")
        habit = await habit_queries.get_habit(pool, habit_id)
        
        streak_msg = f" Current streak: *{habit['streak_count']}* 🔥" if habit['streak_count'] > 0 else ""
        return f"Nice work\\! Logged *{escape_md(habit['name'])}* for today\\.{streak_msg}", None

    elif intent == "delete_habit":
        habit_id = data.get("id")
        search_name = str(data.get("name") or data.get("title") or data.get("query") or "")
        
        if not habit_id and search_name:
            if search_name.isdigit():
                habit_id = int(search_name)
            else:
                matches = await habit_queries.get_habits_by_name(pool, search_name)
                if len(matches) == 1:
                    habit_id = matches[0]['id']
                elif len(matches) > 1:
                    from bot.keyboards import habit_list_keyboard
                    return f"I found multiple habits named *{escape_md(search_name)}*. Which one do you want to delete?", habit_list_keyboard(matches)

        if not habit_id:
            return "Which habit should I delete?", None
            
        habit = await habit_queries.get_habit(pool, habit_id)
        if not habit:
            return "I couldn't find that habit\\.", None
            
        from core.state import set_state
        await set_state(pool, "awaiting_confirmation", "habits", "delete", habit_id)
        
        from bot.keyboards import confirmation_keyboard
        return f"Are you sure you want to delete the habit *{escape_md(habit['name'])}* and all its history?", confirmation_keyboard("habits", "delete", habit_id)

    elif intent == "habit_heatmap":
        photo_bytes, error = await generate_habit_heatmap(pool)
        if error:
            return error, None
        
        if isinstance(photo_bytes, str): # Error message
            return photo_bytes, None
            
        if bot:
            from io import BytesIO
            from core.config import TELEGRAM_USER_ID
            photo = BytesIO(photo_bytes)
            await bot.send_photo(
                chat_id=TELEGRAM_USER_ID,
                photo=photo,
                caption="Habit Streaks 🔥"
            )
            return None, None
        return "Am generat heatmap-ul, dar nu am acces la bot pentru a-l trimite.", None

    return "I'm not sure how to handle that habit request yet\\.", None

async def generate_habit_heatmap(pool) -> tuple[bytes | str, None]:
    data = await habit_queries.get_habit_history_365(pool)
    
    if not data:
        return "Nu există date de habits pentru ultimele 365 zile.", None
    
    # Calculează zilele — 365 zile (ultimul an)
    today = date.today()
    start = today - timedelta(days=364)
    all_days = [start + timedelta(days=i) for i in range(365)]
    
    habits = list(data.keys())
    n_habits = len(habits)
    
    # Calculează dimensiunea figurii: 20 lățime, 2.5 înălțime per habit
    fig, axes = plt.subplots(n_habits, 1, figsize=(15, 2.5 * n_habits))
    if n_habits == 1:
        axes = [axes]
    
    fig.patch.set_facecolor('#0d1117')
    
    # Github colors: empty, level 1 (only two used here)
    colors = ['#161b22', '#39d353'] # empty, done
    
    for ax, habit in zip(axes, habits):
        ax.set_facecolor('#0d1117')
        done_dates = set(data[habit])
        
        # Streak curent
        streak = 0
        d = today
        while d in done_dates:
            streak += 1
            d -= timedelta(days=1)
        
        # Grid logic
        weeks = []
        week = []
        
        # Padding for first week (Monday start)
        for _ in range(start.weekday()):
            week.append(None)
            
        for day in all_days:
            week.append(day)
            if day.weekday() == 6: # Sunday
                weeks.append(week)
                week = []
        if week:
            # Pad the last week
            while len(week) < 7:
                week.append(None)
            weeks.append(week)
        
        for w_idx, week in enumerate(weeks):
            for d_idx, day in enumerate(week):
                if day is None:
                    continue
                
                color = colors[1] if day in done_dates else colors[0]
                
                # Fancy patches for rounded squares
                rect = mpatches.FancyBboxPatch(
                    (w_idx * 14, (6 - d_idx) * 14),
                    11, 11,
                    boxstyle="round,pad=0.5",
                    facecolor=color,
                    edgecolor='none'
                )
                ax.add_patch(rect)
        
        ax.set_xlim(-5, len(weeks) * 14 + 5)
        ax.set_ylim(-5, 7 * 14 + 5)
        ax.axis('off')
        ax.set_title(
            f"{habit}  •  streak curent: {streak} zile",
            color='#e6edf3',
            fontsize=14,
            loc='left',
            pad=10,
            fontweight='bold'
        )
    
    plt.suptitle(
        "Habit Streaks — ultimele 365 zile",
        color='#e6edf3',
        fontsize=18,
        fontweight='bold',
        y=1.02
    )
    plt.tight_layout()
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', facecolor='#0d1117', 
                bbox_inches='tight', dpi=120)
    plt.close()
    return buf.getvalue(), None
