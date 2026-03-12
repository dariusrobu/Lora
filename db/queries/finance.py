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
            SELECT category, SUM(amount) as total 
            FROM finances 
            WHERE type = 'expense' AND EXTRACT(MONTH FROM tx_date) = $1 AND EXTRACT(YEAR FROM tx_date) = $2
            GROUP BY category 
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

async def delete_finance(pool, finance_id: int):
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM finances WHERE id = $1", finance_id)
