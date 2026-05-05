from typing import List, Dict, Any, Optional
from datetime import date
import decimal
from core.utils import with_retry


# ── Categories CRUD ───────────────────────────────────────────


@with_retry(max_attempts=3, base_delay=1.0)
async def add_category(
    pool, name: str, icon: str = "💰", keywords: Optional[List[str]] = None
) -> int:
    """Adds a new finance category."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """INSERT INTO finance_categories (name, icon, keywords)
            VALUES ($1, $2, $3) ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name
            RETURNING id""",
            name,
            icon,
            keywords or [name.lower()],
        )
        return row["id"]


async def list_categories(pool) -> List[Dict[str, Any]]:
    """Lists all active finance categories."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT * FROM finance_categories WHERE is_active = TRUE ORDER BY name"""
        )
        return [dict(r) for r in rows]


async def delete_category(pool, name: str) -> bool:
    """Soft-deletes a finance category."""
    async with pool.acquire() as conn:
        result = await conn.execute(
            """UPDATE finance_categories SET is_active = FALSE WHERE name ILIKE $1""",
            name,
        )
        return result != "UPDATE 0"


async def get_category_by_name(pool, name: str) -> Optional[Dict[str, Any]]:
    """Gets a category by name."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """SELECT * FROM finance_categories WHERE name ILIKE $1 AND is_active = TRUE""",
            name,
        )
        return dict(row) if row else None


async def detect_category_from_text(pool, text: str) -> Optional[str]:
    """Detects a category from text using keywords."""
    text_lower = text.lower()
    categories = await list_categories(pool)
    for cat in categories:
        keywords = cat.get("keywords") or []
        if any(kw in text_lower for kw in keywords):
            return cat["name"]
    return "altele"


# ── Transactions ─────────────────────────────────────────────


@with_retry(max_attempts=3, base_delay=1.0)
async def log_transaction(
    pool,
    tx_type: str,
    amount: float,
    category: str,
    description: str = None,
    tx_date: date = None,
):
    """Logs a new finance transaction."""
    if tx_date is None:
        tx_date = date.today()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO finances (type, amount, category, description, tx_date)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id
            """,
            tx_type,
            decimal.Decimal(str(amount)),
            category,
            description,
            tx_date,
        )
        return row["id"]


async def get_daily_total(pool, log_date: date, tx_type: str = "expense") -> float:
    """Gets total for a specific type on a specific date."""
    async with pool.acquire() as conn:
        val = await conn.fetchval(
            "SELECT SUM(amount) FROM finances WHERE tx_date = $1 AND type = $2",
            log_date,
            tx_type,
        )
        return float(val or 0)


async def get_daily_transactions(pool, log_date: date) -> List[Dict[str, Any]]:
    """Gets all transactions for a specific date."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM finances WHERE tx_date = $1 ORDER BY created_at ASC",
            log_date,
        )
        return [dict(r) for r in rows]


async def get_monthly_category_totals(
    pool, month: int, year: int
) -> List[Dict[str, Any]]:
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
            month,
            year,
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


async def get_monthly_summary(pool, month: int, year: int) -> Dict[str, float]:
    """Gets total income and total expenses for a specific month."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT 
                COALESCE(SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END), 0) as income,
                COALESCE(SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END), 0) as expense
            FROM finances
            WHERE EXTRACT(MONTH FROM tx_date) = $1 
              AND EXTRACT(YEAR FROM tx_date) = $2
            """,
            month,
            year,
        )
        return {"income": float(row["income"]), "expense": float(row["expense"])}


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
            int(days),
        )
        return [dict(r) for r in rows]


@with_retry(max_attempts=3, base_delay=1.0)
async def set_budget_limit(pool, category: str, limit: float):
    """Sets or updates a budget limit for a category."""
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO budget_limits (category, monthly_limit)
            VALUES ($1, $2)
            ON CONFLICT (LOWER(category)) DO UPDATE SET monthly_limit = EXCLUDED.monthly_limit
            """,
            category,
            limit,
        )


async def get_last_transaction_id(pool) -> Optional[int]:
    """Returns the ID of the most recently created transaction."""
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "SELECT id FROM finances ORDER BY created_at DESC LIMIT 1"
        )


async def get_recent_transactions(pool, limit: int = 20) -> List[Dict[str, Any]]:
    """Retrieves the most recent transactions across all categories."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, type, amount, category, description, tx_date, created_at
            FROM finances
            ORDER BY created_at DESC
            LIMIT $1
            """,
            limit,
        )
        return [dict(r) for r in rows]


async def delete_transaction(pool, tx_id: int) -> bool:
    """Deletes a specific transaction by ID."""
    async with pool.acquire() as conn:
        result = await conn.execute("DELETE FROM finances WHERE id = $1", tx_id)
        return result != "DELETE 0"
