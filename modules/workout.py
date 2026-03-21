# modules/workout.py

from typing import Dict, Any, Tuple
import db.queries.workout as workout_queries
from bot.formatter import escape_md
from datetime import date

async def handle_workout_intent(pool, intent: str, data: Dict[str, Any], bot=None) -> Tuple[str, None]:
    
    if intent == "workout_log":
        date_str = data.get("date")
        if date_str:
            try:
                workout_date = date.fromisoformat(date_str)
            except ValueError:
                workout_date = date.today()
        else:
            workout_date = date.today()
            
        workout_type = data.get("type", "gym")
        duration = data.get("duration_min")
        notes = data.get("notes")
        exercises = data.get("exercises", [])
        
        workout_id = await workout_queries.log_workout(
            pool, workout_date, workout_type, duration, notes
        )
        
        for ex in exercises:
            await workout_queries.log_exercise(
                pool, workout_id,
                ex.get("name", ""),
                ex.get("sets"),
                ex.get("reps"),
                ex.get("weight_kg")
            )
        
        return data.get("_original_reply", "Antrenament salvat. 💪"), None

    elif intent == "workout_list":
        workouts = await workout_queries.get_recent_workouts(pool, days=7)
        if not workouts:
            return "Niciun antrenament în ultimele 7 zile.", None
        
        lines = ["💪 *Antrenamente — ultimele 7 zile*\n"]
        for w in workouts:
            date_str = escape_md(str(w['workout_date']))
            type_str = escape_md(w['type'] or "gym")
            dur = f" · {w['duration_min']}min" if w['duration_min'] else ""
            lines.append(f"*{date_str}* — {type_str}{escape_md(dur)}")
            
            if w['exercises']:
                for ex in w['exercises']:
                    if not ex.get('name'):
                        continue
                    ex_line = f"  · {escape_md(ex['name'])}"
                    if ex.get('sets') and ex.get('reps'):
                        ex_line += f" {ex['sets']}×{ex['reps']}"
                    if ex.get('weight_kg'):
                        ex_line += f" @ {ex['weight_kg']}kg"
                    lines.append(ex_line)
        
        return "\n".join(lines), None

    elif intent == "workout_stats":
        stats = await workout_queries.get_workout_stats(pool, days=30)
        if not stats or not stats.get('total_sessions'):
            return "Nu sunt suficiente date de antrenament \\(minim 1 sesiune\\).", None
        
        lines = [
            "📊 *Stats antrenamente — 30 zile*\n",
            f"• Sesiuni totale: *{stats['total_sessions']}*",
            f"• Zile active: *{stats['active_days']}*",
            f"• Tip dominant: *{escape_md(stats['most_common_type'] or 'N/A')}*",
            f"• Durată medie: *{stats['avg_duration'] or 'N/A'} min*",
        ]
        return "\n".join(lines), None

    return "Nu am înțeles cererea legată de antrenamente.", None
