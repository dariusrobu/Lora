from typing import List, Optional, Dict, Any
from datetime import date

async def add_finance(pool, type: str, amount: float, category: str, description: Optional[str] = None, tx_date: date = None) -> int:
    if not tx_date: tx_date = date.today()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO finances (type, amount, category, description, tx_date)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id
            """,
            type, amount, category, description, tx_date
        )
        return row['id']

async def get_monthly_summary(pool, month: int, year: int) -> Dict[str, Any]:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT type, SUM(amount) as total 
            FROM finances 
            WHERE EXTRACT(MONTH FROM tx_date) = $1 AND EXTRACT(YEAR FROM tx_date) = $2
            GROUP BY type
            """,
            month, year
        )
        summary = {"income": 0, "expense": 0}
        for r in rows:
            summary[r['type']] = float(r['total'])
        
        # Breakdown
        breakdown = await conn.fetch(
            """
            SELECT LOWER(category) as category, SUM(amount) as total 
            FROM finances 
            WHERE type = 'expense' AND EXTRACT(MONTH FROM tx_date) = $1 AND EXTRACT(YEAR FROM tx_date) = $2
            GROUP BY LOWER(category) 
            ORDER BY total DESC
            """,
            month, year
        )
        summary['breakdown'] = [dict(r) for r in breakdown]
        return summary

async def get_budget_limit(pool, category: str) -> Optional[float]:
    async with pool.acquire() as conn:
        val = await conn.fetchval("SELECT monthly_limit FROM budget_limits WHERE category = $1", category)
        return float(val) if val else None

async def get_recent_finances(pool, limit: int = 10) -> List[Dict[str, Any]]:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, type, amount, category, description, tx_date
            FROM finances
            ORDER BY tx_date DESC, id DESC
            LIMIT $1
            """,
            limit
        )
        return [dict(r) for r in rows]

async def delete_finance(pool, finance_id: int):
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM finances WHERE id = $1", finance_id)

async def get_weekly_finance_summary(pool, start_date: date, end_date: date) -> Dict[str, Any]:
    """Returns total expense and top category for the week."""
    async with pool.acquire() as conn:
        total = await conn.fetchval(
            "SELECT SUM(amount) FROM finances WHERE type = 'expense' AND tx_date BETWEEN $1 AND $2",
            start_date, end_date
        )
        top = await conn.fetchrow(
            """
            SELECT category, SUM(amount) as amount 
            FROM finances 
            WHERE type = 'expense' AND tx_date BETWEEN $1 AND $2 
            GROUP BY category 
            ORDER BY amount DESC 
            LIMIT 1
            """,
            start_date, end_date
        )
        return {
            "total": float(total) if total else 0,
            "top_category": top['category'] if top else None
        }

async def get_monthly_total_by_category(pool, category: str) -> float:
    """Returns the total expense for a category in the current month."""
    async with pool.acquire() as conn:
        val = await conn.fetchval(
            """
            SELECT SUM(amount) 
            FROM finances 
            WHERE type = 'expense' AND LOWER(category) = LOWER($1)
            AND EXTRACT(MONTH FROM tx_date) = EXTRACT(MONTH FROM CURRENT_DATE)
            AND EXTRACT(YEAR FROM tx_date) = EXTRACT(YEAR FROM CURRENT_DATE)
            """,
            category
        )
        return float(val) if val else 0.0

async def update_budget_alert_flags(pool, category: str, alerted_80: bool, alerted_100: bool):
    """Persists alert state for a category."""
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE budget_limits SET alerted_80 = $1, alerted_100 = $2 WHERE category = $3",
            alerted_80, alerted_100, category
        )

async def reset_all_budget_alerts(pool):
    """Resets all alert flags for the new month."""
    async with pool.acquire() as conn:
        await conn.execute("UPDATE budget_limits SET alerted_80 = FALSE, alerted_100 = FALSE")

async def set_budget(pool, category: str, limit: float):
    """Upserts a budget limit and resets alerts. Category is forced lower."""
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO budget_limits (category, monthly_limit, alerted_80, alerted_100)
            VALUES (LOWER($1), $2, FALSE, FALSE)
            ON CONFLICT ON CONSTRAINT budget_limits_category_unique DO UPDATE 
            SET monthly_limit = $2, alerted_80 = FALSE, alerted_100 = FALSE
            """,
            category, limit
        )

async def get_budget_status(pool, category: str) -> Optional[Dict[str, Any]]:
    """Returns limit and alert flags for a category (case-insensitive)."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT monthly_limit, alerted_80, alerted_100 FROM budget_limits WHERE LOWER(category) = LOWER($1)",
            category
        )
        return dict(row) if row else None
