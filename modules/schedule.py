# modules/schedule.py

from typing import Dict, Any, Tuple
import db.queries.schedule as schedule_queries
from bot.formatter import escape_md


async def handle_schedule_intent(
    pool, intent: str, data: Dict[str, Any], bot=None
) -> Tuple[str, None]:

    if intent == "schedule_today":
        classes = await schedule_queries.get_today_schedule(pool)
        week_type = await schedule_queries.get_current_week_type(pool)
        week_label = "impară" if week_type == "odd" else "pară"

        if not classes:
            return f"Nu ai cursuri azi \\(săptămână {week_label}\\)\\. 🎉", None

        lines = [f"📚 *Cursuri azi* — săptămână {week_label}\n"]
        for c in classes:
            start = c["start_time"].strftime("%H:%M")
            end = c["end_time"].strftime("%H:%M")
            room = f" · sala *{escape_md(c['room'])}*" if c.get("room") else ""
            type_str = "📖" if c["class_type"] == "curs" else "✏️"
            lines.append(
                f"{type_str} `{start}–{end}` *{escape_md(c['subject_name'])}*{room}"
            )

        return "\n".join(lines), None

    elif intent == "schedule_week":
        week_schedule, days, week_type = await schedule_queries.get_week_schedule(pool)
        week_label = "impară" if week_type == "odd" else "pară"

        lines = [f"📅 *Orar săptămâna aceasta* — săptămână {week_label}\n"]

        for day_idx, day_name in days.items():
            classes = week_schedule.get(day_idx, [])
            if not classes:
                continue
            lines.append(f"*{day_name}*")
            for c in classes:
                start = c["start_time"].strftime("%H:%M")
                end = c["end_time"].strftime("%H:%M")
                room = f" · {escape_md(c['room'])}" if c.get("room") else ""
                type_icon = "📖" if c["class_type"] == "curs" else "✏️"
                lines.append(
                    f"  {type_icon} `{start}` {escape_md(c['subject_name'])}{room}"
                )
            lines.append("")

        return "\n".join(lines), None

    return "Nu am înțeles cererea legată de orar\\.", None
