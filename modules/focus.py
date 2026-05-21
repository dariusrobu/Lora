# modules/focus.py

from typing import Dict, Any, Tuple
from datetime import datetime
import db.queries.focus as focus_queries
from bot.formatter import escape_md
from core.config import TELEGRAM_USER_ID, TIMEZONE
import pytz


async def handle_focus_intent(
    pool, intent: str, data: Dict[str, Any], bot=None
) -> Tuple[str, None]:

    if intent == "focus_start":
        duration = data.get("duration_min", 25)
        task = data.get("task_description")

        session_id = await focus_queries.start_session(pool, duration, task)

        # Salvează session_id în conversation state pentru a-l folosi la final
        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE conversation_state 
                SET state_type = 'in_focus_session',
                    module = 'focus',
                    action = 'complete',
                    item_id = $1,
                    created_at = NOW()
                WHERE state_key = 'current'
            """,
                session_id,
            )

        # Scheduleaza job one-shot
        if bot:
            from apscheduler.triggers.date import DateTrigger
            from datetime import timedelta

            user_tz = pytz.timezone(TIMEZONE)
            end_time = datetime.now(user_tz) + timedelta(minutes=duration)

            # Folosim bot_data scheduler dacă există
            scheduler = None
            try:
                from scheduler.jobs import _global_scheduler

                scheduler = _global_scheduler
            except ImportError:
                pass

            if scheduler:
                scheduler.add_job(
                    send_focus_end,
                    trigger=DateTrigger(run_date=end_time),
                    args=[bot, pool, session_id, duration],
                    id=f"focus_{session_id}",
                    replace_existing=True,
                )

        task_str = f" — *{escape_md(task)}*" if task else ""
        return f"✅ Focus pornit: *{duration} min*{task_str}\\.", None

    elif intent == "focus_stop":
        from core.state import get_state, clear_state

        state = await get_state(pool)

        if not state or state.get("state_type") != "in_focus_session":
            return "⚠️ Atenție: Nu ai nicio sesiune de focus activă\\.", None

        session_id = state.get("item_id")
        user_tz = pytz.timezone(TIMEZONE)
        now = datetime.now(user_tz)

        # Calculează minutele scurse
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT created_at, duration_min FROM focus_sessions WHERE id = $1",
                session_id,
            )
        if row:
            elapsed = int(
                (now - row["created_at"].replace(tzinfo=pytz.utc)).total_seconds() / 60
            )
            total = row["duration_min"]
            await focus_queries.interrupt_session(pool, session_id, elapsed)

            # Tough Love Reaction
            import db.queries.profile as profile_queries

            profile = await profile_queries.get_user_profile(pool, TELEGRAM_USER_ID)
            tone = profile.get("tone", "warm")

            penalty = ""
            if tone == "direct":
                penalty = f"\n\n🔥 *PENIBIL\!* Ai rezistat doar {elapsed}/{total} minute\. Concentrarea ta e la pământ\. Data viitoare nu mă mai pune să pornesc timer-ul dacă n-ai de gând să muncești\!"
            else:
                penalty = f"\n\n⚠️ Atenție: Sesiune întreruptă la minutul {elapsed}/{total}\\. Încearcă să fii mai concentrat data viitoare\\."

            # Try to remove the scheduled job if possible
            try:
                from scheduler.jobs import _global_scheduler

                if _global_scheduler and _global_scheduler.get_job(
                    f"focus_{session_id}"
                ):
                    _global_scheduler.remove_job(f"focus_{session_id}")
            except Exception:
                pass

        await clear_state(pool)
        return f"🛑 Sesiune întreruptă\\.{penalty}", None

    elif intent == "focus_list":
        sessions = await focus_queries.get_recent_sessions(pool, days=7)
        if not sessions:
            return "ℹ️ Nicio sesiune de focus în ultimele 7 zile\\.", None

        completed = [s for s in sessions if s["completed"]]
        total_min = sum(s["duration_min"] for s in completed)
        total_h = total_min // 60
        total_m = total_min % 60

        lines = ["⏱ *Focus Sessions — ultimele 7 zile*\n"]
        lines.append(f"• Sesiuni completate: *{len(completed)}/{len(sessions)}*")
        lines.append(f"• Timp total focus: *{total_h}h {total_m}min*\n")

        for s in sessions[:5]:
            status = (
                "✅" if s["completed"] else ("⚠️" if s.get("interrupted_at") else "⬜")
            )
            task = (
                f" — {escape_md(s['task_description'])}"
                if s.get("task_description")
                else ""
            )
            date_str = escape_md(str(s["session_date"]))
            lines.append(f"{status} *{date_str}* · {s['duration_min']}min{task}")

        return "\n".join(lines), None

    return "❌ Eroare: Nu am înțeles cererea legată de focus\\.", None


async def send_focus_end(bot, pool, session_id: int, duration: int) -> None:
    """Job one-shot — trimis la finalul sesiunii de focus."""
    try:
        await bot.send_message(
            chat_id=TELEGRAM_USER_ID,
            text=f"⏰ *{duration} minute de focus încheiate\\.*\n\nCe ai reușit să faci?",
            parse_mode="MarkdownV2",
        )

        # Setează state pentru a captura răspunsul
        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE conversation_state 
                SET state_type = 'awaiting_focus_result',
                    module = 'focus',
                    action = 'complete',
                    item_id = $1,
                    created_at = NOW()
                WHERE state_key = 'current'
            """,
                session_id,
            )

    except Exception as e:
        print(f"Focus end notification error: {e}", flush=True)
