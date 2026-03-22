# modules/insights.py

import asyncio
from typing import Optional
from datetime import date, timedelta
import db.queries.health as health_queries
import db.queries.habits as habit_queries
import db.queries.goals as goal_queries
import db.queries.tasks as task_queries

async def get_recent_insight_types(pool, days=5) -> set:
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT insight_type FROM insight_log
            WHERE sent_at >= NOW() - $1 * INTERVAL '1 day'
        """, days)
        return {r['insight_type'] for r in rows}

async def log_insight(pool, insight_type: str) -> None:
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO insight_log (insight_type) VALUES ($1)
        """, insight_type)

async def check_sleep_alert(pool, recent_types: set) -> Optional[tuple]:
    if 'sleep_low' in recent_types:
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
        
        if all(r['sleep_hours'] and r['sleep_hours'] < 6.5 for r in rows):
            return 'sleep_low', "3 nopți consecutive sub 6\\.5h somn\\."
    return None

async def check_goal_stale(pool, recent_types: set) -> Optional[tuple]:
    if 'goal_stale' in recent_types:
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
        title = escape_md(rows[0]['title'])
        return 'goal_stale', f"Goalul *{title}* e blocat de 2 săptămâni\\."

async def check_habit_streak_broken(pool, recent_types: set) -> Optional[tuple]:
    if 'habit_streak_broken' in recent_types:
        return None
    
    yesterday = date.today() - timedelta(days=1)
    habits = await habit_queries.list_habits(pool)
    
    async with pool.acquire() as conn:
        for h in habits:
            if h.get('streak_count', 0) == 0:
                # Check if had streak of 7+ before yesterday
                row = await conn.fetchrow("""
                    SELECT COUNT(*) as streak
                    FROM habit_logs
                    WHERE habit_id = $1
                      AND log_date BETWEEN CURRENT_DATE - INTERVAL '8 days' 
                          AND CURRENT_DATE - INTERVAL '2 days'
                      AND status = 'done'
                """, h['id'])
                
                if row and row['streak'] >= 7:
                    from bot.formatter import escape_md
                    name = escape_md(h['name'])
                    return 'habit_streak_broken', f"Ai rupt streak\\-ul de 7\\+ zile la *{name}*\\."
    
    return None

async def check_water_low(pool, recent_types: set) -> Optional[tuple]:
    if 'water_low' in recent_types:
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
        
        if all(r['water_ml'] and r['water_ml'] < 1000 for r in rows):
            return 'water_low', "Sub 1L apă 3 zile la rând\\."
    return None

async def check_overdue_tasks(pool, recent_types: set) -> Optional[tuple]:
    if 'tasks_overdue' in recent_types:
        return None
    
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT COUNT(*) as count FROM tasks
            WHERE due_date < CURRENT_DATE
              AND status != 'done'
        """)
        
        if row and row['count'] >= 5:
            return 'tasks_overdue', f"{row['count']} tasks overdue de peste 5 zile\\."
    
    return None

async def check_attendance_warning(pool, recent_types: set) -> Optional[tuple]:
    if 'attendance_warning' in recent_types:
        return None
    
    from db.queries.university import get_attendance_warnings
    warnings = await get_attendance_warnings(pool)
    
    if not warnings:
        return None
    
    names = ", ".join(w['name'] for w in warnings[:2])
    from bot.formatter import escape_md
    return 'attendance_warning', f"Prezențe sub minim la: *{escape_md(names)}*\\."

async def generate_insights(pool) -> str:
    """Generează insights pentru weekly review (text simplu)."""
    recent_types = await get_recent_insight_types(pool, days=7)
    
    checks = await asyncio.gather(
        check_sleep_alert(pool, recent_types),
        check_water_low(pool, recent_types),
        check_overdue_tasks(pool, recent_types),
    )
    
    insights = [c[1] for c in checks if c]
    
    if not insights:
        return "Nu am suficiente date pentru patterns semnificative."
    
    return "\n".join(f"• {i}" for i in insights[:2])

async def run_proactive_insights(pool, bot) -> None:
    """Rulează toate check-urile și trimite max 2 insights per zi."""
    from core.config import TELEGRAM_USER_ID
    
    recent_types = await get_recent_insight_types(pool, days=5)
    
    checks = await asyncio.gather(
        check_sleep_alert(pool, recent_types),
        check_goal_stale(pool, recent_types),
        check_habit_streak_broken(pool, recent_types),
        check_water_low(pool, recent_types),
        check_overdue_tasks(pool, recent_types),
        check_attendance_warning(pool, recent_types),
    )
    
    insights = [c for c in checks if c]
    
    if not insights:
        return
    
    # Max 2 insights per zi
    to_send = insights[:2]
    
    lines = []
    for insight_type, message in to_send:
        lines.append(f"• {message}")
        await log_insight(pool, insight_type)
    
    text = "💡 *Câteva observații:*\n\n" + "\n".join(lines)
    
    await bot.send_message(
        chat_id=TELEGRAM_USER_ID,
        text=text,
        parse_mode="MarkdownV2"
    )
