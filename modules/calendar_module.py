from typing import Dict, Any, Tuple, Optional
from datetime import datetime
import core.icloud as calendar_core
from bot.formatter import escape_md
import asyncio


async def handle_calendar_intent(
    pool, intent: str, data: Dict[str, Any]
) -> Tuple[str, Optional[Any]]:
    """Handler for calendar-related intents."""

    if intent == "calendar_today":
        events = await calendar_core.fetch_all_calendars_events(days_ahead=1)
        if not events:
            return "📅 Nu ai evenimente planificate pentru azi în Apple Calendar.", None

        lines = ["📅 *Evenimente Azi (Apple Calendar):*"]
        for e in events:
            time_str = e["start"].strftime("%H:%M")
            lines.append(
                f"• `{time_str}` — {escape_md(e['summary'])} \\(_{escape_md(e['calendar'])}_\\)"
            )

        return "\n".join(lines), None

    elif intent == "calendar_week":
        events = await calendar_core.fetch_all_calendars_events(days_ahead=7)
        if not events:
            return "📅 Nu ai evenimente planificate săptămâna aceasta.", None

        lines = ["📅 *Evenimente Săptămâna Aceasta:*"]
        current_date = None
        for e in events:
            event_date = e["start"].date()
            if event_date != current_date:
                current_date = event_date
                lines.append(f"\n🗓 *{event_date.strftime('%d %b')}*")

            time_str = e["start"].strftime("%H:%M")
            lines.append(
                f"• `{time_str}` — {escape_md(e['summary'])} \\(_{escape_md(e['calendar'])}_\\)"
            )

        return "\n".join(lines), None

    elif intent == "calendar_add":
        summary = data.get("summary")
        start_str = data.get("start")
        end_str = data.get("end")
        location = data.get("location")
        description = data.get("description")

        if not summary or not start_str:
            return (
                "❌ Am nevoie de un titlu și o oră pentru a adăuga în calendar.",
                None,
            )

        try:
            start_dt = datetime.fromisoformat(start_str)
            if start_dt.tzinfo is None:
                start_dt = calendar_core.LOCAL_TZ.localize(start_dt)

            end_dt = None
            if end_str:
                end_dt = datetime.fromisoformat(end_str)
                if end_dt.tzinfo is None:
                    end_dt = calendar_core.LOCAL_TZ.localize(end_dt)

            await calendar_core.create_event(
                summary=summary,
                start=start_dt,
                end=end_dt,
                location=location,
                description=description,
            )

            return (
                f"✅ Eveniment adăugat în Apple Calendar: *{escape_md(summary)}*\n⏰ {start_dt.strftime('%H:%M')}",
                None,
            )
        except Exception as e:
            return f"❌ Eroare la adăugarea în calendar: {str(e)}", None

    elif intent == "calendar_sync":
        # Manual sync trigger
        results = await asyncio.gather(
            calendar_core.cleanup_calendar_orphans(pool),
            calendar_core.sync_university_schedule_to_calendar(pool),
            calendar_core.sync_events_table_to_calendar(pool),
            calendar_core.sync_tasks_with_deadlines(pool),
            calendar_core.sync_exams_to_calendar(pool),
            calendar_core.sync_from_icloud_to_lora(pool), # Bi-directional
        )

        c_stats, s_stats, e_stats, t_stats, ex_stats, b_stats = results
        total_created = s_stats["created"] + e_stats["created"] + t_stats["created"] + ex_stats["created"]

        msg = (
            f"🔄 *Sincronizare Apple Calendar completă*\n\n"
            f"• 🎓 Cursuri: {s_stats['created']} noi\n"
            f"• 🎓 Examene: {ex_stats['created']} noi\n"
            f"• 📅 Evenimente/Reminders: {e_stats['created']} noi\n"
            f"• 📋 Task\\-uri: {t_stats['created']} noi\n"
            f"• 🧹 Curățate: {c_stats['deleted']} elemente șterse\n"
            f"• 📥 Actualizate din iCloud: {b_stats['updated']} modificări preluate\n"
            f"\nTotal exportat: {total_created} elemente ✓"
        )
        return msg, None

    return "Intent calendar nerecunoscut.", None
