from typing import List, Dict, Any, Optional
from datetime import date, datetime
import decimal

async def log_transaction(pool, tx_type: str, amount: float, category: str, description: str = None, tx_date: date = None):
    """Logs a new finance transaction."""
    if tx_date is None:
        tx_date = date.today()
        
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO finances (type, amount, category, description, tx_date)
            VALUES ($1, $2, $3, $4, $5)
            """,
            tx_type, decimal.Decimal(str(amount)), category, description, tx_date
        )

async def get_daily_total(pool, log_date: date, tx_type: str = 'expense') -> float:
    """Gets total for a specific type on a specific date."""
    async with pool.acquire() as conn:
        val = await conn.fetchval(
            "SELECT SUM(amount) FROM finances WHERE tx_date = $1 AND type = $2",
            log_date, tx_type
        )
        return float(val or 0)

async def get_daily_transactions(pool, log_date: date) -> List[Dict[str, Any]]:
    """Gets all transactions for a specific date."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM finances WHERE tx_date = $1 ORDER BY created_at ASC",
            log_date
        )
        return [dict(r) for r in rows]

async def get_monthly_category_totals(pool, month: int, year: int) -> List[Dict[str, Any]]:
    """Gets category totals for a specific month."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT category, SUM(amount) as total
            FROM finances
            WHERE EXTRACT(MONTH FROM tx_date) = $1 
              AND EXTRACT(YEAR FROM tx_date) = $2
              AND type = 'expense'
            GROUP BY category
            ORDER BY total DESC
            """,
            month, year
        )
        return [dict(r) for r in rows]

async def get_budget_status(pool) -> List[Dict[str, Any]]:
    """Gets current month spending vs limits for all categories with limits."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT 
                bl.category, 
                bl.monthly_limit,
                COALESCE(SUM(f.amount), 0) as current_spent
            FROM budget_limits bl
            LEFT JOIN finances f ON LOWER(f.category) = LOWER(bl.category) 
                AND f.type = 'expense'
                AND EXTRACT(MONTH FROM f.tx_date) = EXTRACT(MONTH FROM CURRENT_DATE)
                AND EXTRACT(YEAR FROM f.tx_date) = EXTRACT(YEAR FROM CURRENT_DATE)
            GROUP BY bl.category, bl.monthly_limit
            """
        )
        return [dict(r) for r in rows]

async def get_finance_history(pool, days: int = 30) -> List[Dict[str, Any]]:
    """Retrieves daily spending history."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT tx_date, SUM(amount) as total
            FROM finances
            WHERE tx_date > CURRENT_DATE - $1::integer
              AND type = 'expense'
            GROUP BY tx_date
            ORDER BY tx_date ASC
            """,
            int(days)
        )
        return [dict(r) for r in rows]
