# modules/insights.py

import asyncio
from typing import Optional


async def get_recent_insight_types(pool, days=5) -> set:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT insight_type FROM insight_log
            WHERE sent_at >= NOW() - $1 * INTERVAL '1 day'
        """,
            days,
        )
        return {r["insight_type"] for r in rows}


async def log_insight(pool, insight_type: str) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO insight_log (insight_type) VALUES ($1)
        """,
            insight_type,
        )


async def check_sleep_alert(pool, recent_types: set) -> Optional[tuple]:
    if "sleep_low" in recent_types:
        return None

    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT sleep_hours FROM health_logs
            WHERE log_date >= CURRENT_DATE - INTERVAL '3 days'
            ORDER BY log_date DESC
            LIMIT 3
        """)

        if len(rows) < 3:
            return None

        if all(r["sleep_hours"] and r["sleep_hours"] < 6.5 for r in rows):
            return "sleep_low", "3 nopți consecutive sub 6\\.5h somn\\."
    return None


async def check_goal_stale(pool, recent_types: set) -> Optional[tuple]:
    if "goal_stale" in recent_types:
        return None

    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT title, updated_at FROM goals
            WHERE status = 'active'
              AND updated_at < NOW() - INTERVAL '14 days'
            LIMIT 1
        """)

        if not rows:
            return None

        from bot.formatter import escape_md

        title = escape_md(rows[0]["title"])
        return "goal_stale", f"Goalul *{title}* e blocat de 2 săptămâni\\."


async def check_skill_streak_broken(pool, recent_types: set) -> Optional[tuple]:
    # Skills streaks are now tracked in the skills module
    # No proactive insight needed for skill streaks yet
    return None


async def check_water_low(pool, recent_types: set) -> Optional[tuple]:
    if "water_low" in recent_types:
        return None

    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT water_ml FROM health_logs
            WHERE log_date >= CURRENT_DATE - INTERVAL '3 days'
            ORDER BY log_date DESC
            LIMIT 3
        """)

        if len(rows) < 3:
            return None

        if all(r["water_ml"] and r["water_ml"] < 1000 for r in rows):
            return "water_low", "Sub 1L apă 3 zile la rând\\."
    return None


async def check_overdue_tasks(pool, recent_types: set) -> Optional[tuple]:
    if "tasks_overdue" in recent_types:
        return None

    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT COUNT(*) as count FROM tasks
            WHERE due_date < CURRENT_DATE
              AND status != 'done'
        """)

        if row and row["count"] >= 5:
            return "tasks_overdue", f"{row['count']} tasks overdue de peste 5 zile\\."

    return None


async def check_attendance_warning(pool, recent_types: set) -> Optional[tuple]:
    if "attendance_warning" in recent_types:
        return None

    from db.queries.university import get_attendance_warnings

    warnings = await get_attendance_warnings(pool)

    if not warnings:
        return None

    names = ", ".join(w["name"] for w in warnings[:2])
    from bot.formatter import escape_md

    return "attendance_warning", f"Prezențe sub minim la: *{escape_md(names)}*\\."


async def generate_insights(pool) -> str:
    """Generează insights (standard + correlations) la cerere."""
    from core.correlations import compute_correlations
    from bot.formatter import safe_markdown

    recent_types = await get_recent_insight_types(pool, days=7)

    # 1. Run standard checks and correlations in parallel
    results = await asyncio.gather(
        check_sleep_alert(pool, recent_types),
        check_water_low(pool, recent_types),
        check_overdue_tasks(pool, recent_types),
        compute_correlations(pool),
    )

    standard_checks = [c[1] for c in results[:3] if c]
    correlations = results[3]

    final_lines = []

    # Process standard checks
    for i in standard_checks[:2]:
        final_lines.append(f"• {i}")

    # Process correlations
    for corr in correlations[:2]:
        msg = (
            f"🔍 *Pattern detectat:* {corr['correlation']}\n"
            f"📊 *Dovadă:* {corr['data_evidence']}\n"
            f"💡 *Recomandare:* {corr['recommendation']}"
        )
        final_lines.append(msg)

    if not final_lines:
        return "Nu am suficiente date pentru patterns semnificative."

    return safe_markdown("\n\n".join(final_lines))


async def run_proactive_insights(pool, bot) -> None:
    """Rulează toate check-urile și trimite max 2 insights per zi."""
    from core.config import TELEGRAM_USER_ID
    from core.correlations import (
        compute_correlations,
        get_unseen_correlations,
        save_correlation_as_fact,
    )
    from bot.formatter import safe_markdown

    recent_types = await get_recent_insight_types(pool, days=5)

    # 1. Run standard checks
    checks = await asyncio.gather(
        check_sleep_alert(pool, recent_types),
        check_goal_stale(pool, recent_types),
        check_skill_streak_broken(pool, recent_types),
        check_water_low(pool, recent_types),
        check_overdue_tasks(pool, recent_types),
        check_attendance_warning(pool, recent_types),
    )

    insights = [(c[0], c[1]) for c in checks if c]

    # 2. Run Correlation Engine (if enough data)
    try:
        raw_correlations = await compute_correlations(pool)
        new_correlations = await get_unseen_correlations(pool, raw_correlations)

        for corr in new_correlations:
            # We treat correlations as a special type of insight
            msg = (
                f"🔍 *Pattern detectat:* {corr['correlation']}\n"
                f"📊 *Dovadă:* {corr['data_evidence']}\n"
                f"💡 *Recomandare:* {corr['recommendation']}"
            )
            # Use 'correlation' as type prefix + first 10 chars of correlation text to avoid duplicates
            corr_type = f"correlation_{corr['correlation'][:20]}"
            insights.append((corr_type, msg))
            # Also save to memory_facts as a persistent fact
            await save_correlation_as_fact(pool, corr)
    except Exception as e:
        print(f"Error in proactive correlations: {e}", flush=True)

    if not insights:
        return

    # Max 2 insights per zi total
    # Prioritize correlations if present? Or just first 2.
    # Let's pick at most 1 correlation and 1 standard insight, or first 2.
    to_send = insights[:2]

    lines = []
    for insight_type, message in to_send:
        # Standard insights start with bullet, correlations already have emojis
        if not message.startswith("🔍"):
            lines.append(f"• {message}")
        else:
            lines.append(message)

        await log_insight(pool, insight_type)

    text = "💡 *Câteva observații:*\n\n" + "\n\n".join(lines)

    await bot.send_message(
        chat_id=TELEGRAM_USER_ID, text=safe_markdown(text), parse_mode="MarkdownV2"
    )
