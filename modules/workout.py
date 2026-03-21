# modules/workout.py

from typing import Dict, Any, Tuple
import db.queries.workout as workout_queries
from bot.formatter import escape_md
from datetime import date
import json as _json

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
        # Determine period from data
        period = data.get("period", "week")  # "week" | "month" | "long"
        
        if period == "long":
            # Long term view — 6 luni
            stats = await workout_queries.get_long_term_stats(pool, days=180)
            workouts = await workout_queries.get_recent_workouts(pool, days=180)
            
            if not workouts:
                return "Niciun antrenament înregistrat în ultimele 6 luni.", None
            
            lines = ["💪 *Antrenamente — ultimele 6 luni*\n"]
            
            # Overview stats
            total_h = int((stats.get('total_min') or 0) // 60)
            total_m = int((stats.get('total_min') or 0) % 60)
            lines += [
                f"📊 *Overview*",
                f"• Sesiuni totale: *{stats.get('total_sessions', 0)}*",
                f"• Zile active: *{stats.get('active_days', 0)}*",
                f"• Timp total: *{total_h}h {total_m}min*",
                f"• Durată medie: *{stats.get('avg_duration') or 'N/A'} min*",
                f"• Tip dominant: *{escape_md(stats.get('most_common_type') or 'N/A')}*",
                "",
            ]
            
            # Breakdown pe tip
            if stats.get('by_type'):
                lines.append("🏋️ *Pe tip de antrenament*")
                for t in stats['by_type']:
                    t_min = t.get('total_min') or 0
                    t_h = int(t_min // 60)
                    t_m = int(t_min % 60)
                    dur_str = f"{t_h}h {t_m}min" if t_h > 0 else f"{t_m}min"
                    lines.append(f"• {escape_md(t['type'] or 'alt')}: *{t['count']} sesiuni* · {escape_md(dur_str)}")
                lines.append("")
            
            # Top exerciții
            if stats.get('top_exercises'):
                lines.append("🔝 *Top exerciții \\(volum total\\)*")
                for ex in stats['top_exercises']:
                    max_w = f" · max *{ex['max_weight']}kg*" if ex.get('max_weight') else ""
                    lines.append(f"• {escape_md(ex['name'])}: *{ex['times_done']}x*{escape_md(max_w)}")
                lines.append("")
            
            # Trend lunar
            if stats.get('monthly_trend'):
                lines.append("📈 *Trend lunar*")
                for m in stats['monthly_trend']:
                    bar = "█" * min(m['sessions'], 10)
                    lines.append(f"• {escape_md(m['month'])}: {escape_md(bar)} *{m['sessions']}*")
                lines.append("")
            
            # Ultimele 5 antrenamente
            lines.append("🕐 *Ultimele antrenamente*")
            for w in workouts[:5]:
                date_str = escape_md(str(w['workout_date']))
                type_str = escape_md(w['type'] or "gym")
                dur = f" · {w['duration_min']}min" if w['duration_min'] else ""
                lines.append(f"*{date_str}* — {type_str}{escape_md(dur)}")
                if w['exercises']:
                    for ex in w['exercises'][:3]:
                        if isinstance(ex, str):
                            try:
                                ex = _json.loads(ex)
                            except Exception:
                                continue
                        if not ex.get('name'):
                            continue
                        ex_line = f"  · {escape_md(ex['name'])}"
                        if ex.get('sets') and ex.get('reps'):
                            ex_line += f" {ex['sets']}×{ex['reps']}"
                        if ex.get('weight_kg'):
                            ex_line += f" @ {ex['weight_kg']}kg"
                        lines.append(ex_line)
            
            return "\n".join(lines), None
        
        else:
            # Default — ultimele 7 zile
            days = 30 if period == "month" else 7
            workouts = await workout_queries.get_recent_workouts(pool, days=days)
            label = "30 zile" if period == "month" else "7 zile"
            
            if not workouts:
                return f"Niciun antrenament în ultimele {label}.", None
            
            lines = [f"💪 *Antrenamente — ultimele {label}*\n"]
            for w in workouts:
                date_str = escape_md(str(w['workout_date']))
                type_str = escape_md(w['type'] or "gym")
                dur = f" · {w['duration_min']}min" if w['duration_min'] else ""
                lines.append(f"*{date_str}* — {type_str}{escape_md(dur)}")
                if w['exercises']:
                    for ex in w['exercises']:
                        if isinstance(ex, str):
                            try:
                                ex = _json.loads(ex)
                            except Exception:
                                continue
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
