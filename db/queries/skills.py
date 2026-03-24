from typing import List, Dict, Any, Optional
from datetime import date

async def get_all_skills(pool) -> List[Dict[str, Any]]:
    """Returns all skills with their latest log value and date."""
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT s.*, 
                   sl.value as last_value, 
                   sl.metric as last_metric,
                   sl.log_date as last_log_date
            FROM skills s
            LEFT JOIN LATERAL (
                SELECT value, metric, log_date 
                FROM skill_logs 
                WHERE skill_id = s.id 
                ORDER BY log_date DESC, id DESC 
                LIMIT 1
            ) sl ON TRUE
            ORDER BY s.name ASC
        """)
        return [dict(r) for r in rows]

async def get_skill_by_id(pool, skill_id: int) -> Optional[Dict[str, Any]]:
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM skills WHERE id = $1", skill_id)
        return dict(row) if row else None

async def get_skill_by_name(pool, name: str) -> Optional[Dict[str, Any]]:
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM skills WHERE LOWER(name) = LOWER($1)", name.strip())
        return dict(row) if row else None

async def add_skill(pool, name: str, category: str = "General", unit: str = "unit") -> Dict[str, Any]:
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            INSERT INTO skills (name, category, unit)
            VALUES ($1, $2, $3)
            RETURNING *
        """, name.strip(), category, unit)
        return dict(row)

async def delete_skill(pool, skill_id: int) -> bool:
    async with pool.acquire() as conn:
        result = await conn.execute("DELETE FROM skills WHERE id = $1", skill_id)
        return result == "DELETE 1"

async def log_skill_value(pool, skill_id: int, value: float, metric: str = None, log_date: date = None) -> Dict[str, Any]:
    if log_date is None:
        log_date = date.today()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            INSERT INTO skill_logs (skill_id, value, metric, log_date)
            VALUES ($1, $2, $3, $4)
            RETURNING *
        """, skill_id, value, metric, log_date)
        return dict(row)

async def get_skill_history(pool, skill_id: int, limit: int = 10) -> List[Dict[str, Any]]:
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT * FROM skill_logs 
            WHERE skill_id = $1 
            ORDER BY log_date DESC, id DESC 
            LIMIT $2
        """, skill_id, limit)
        return [dict(r) for r in rows]

async def get_skill_stats(pool, skill_id: int) -> Dict[str, Any]:
    """Calculates basic stats and trend."""
    async with pool.acquire() as conn:
        # Get basic aggregates
        stats = await conn.fetchrow("""
            SELECT MIN(value) as min_val, 
                   MAX(value) as max_val, 
                   AVG(value) as avg_val,
                   COUNT(*) as count
            FROM skill_logs 
            WHERE skill_id = $1
        """, skill_id)
        
        # Get last 2 entries for trend
        last_two = await conn.fetch("""
            SELECT value FROM skill_logs 
            WHERE skill_id = $1 
            ORDER BY log_date DESC, id DESC 
            LIMIT 2
        """, skill_id)
        
        trend = 0
        if len(last_two) >= 2:
            trend = float(last_two[0]['value'] - last_two[1]['value'])
            
        return {
            "min": float(stats['min_val']) if stats['min_val'] is not None else 0,
            "max": float(stats['max_val']) if stats['max_val'] is not None else 0,
            "avg": float(stats['avg_val']) if stats['avg_val'] is not None else 0,
            "count": stats['count'],
            "trend": trend
        }

async def get_skill_streak(pool, skill_id: int) -> int:
    """Calculates the current consecutive daily streak for a skill."""
    from datetime import date, timedelta
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT DISTINCT log_date 
            FROM skill_logs 
            WHERE skill_id = $1 
            ORDER BY log_date DESC
        """, skill_id)
        
        if not rows:
            return 0
            
        dates = [r['log_date'] for r in rows]
        today = date.today()
        
        # If the most recent log is older than yesterday, streak is broken
        if (today - dates[0]).days > 1:
            return 0
                
        streak = 0
        current_date = dates[0]
        
        for d in dates:
            if d == current_date:
                streak += 1
                current_date -= timedelta(days=1)
            else:
                break
        return streak
