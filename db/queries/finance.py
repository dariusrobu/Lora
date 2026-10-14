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
    receipt_telegram_file_id: Optional[str] = None,
    receipt_local_path: Optional[str] = None,
):
    """Logs a new finance transaction."""
    if tx_date is None:
        tx_date = date.today()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO finances (
                type, amount, category, description, tx_date,
                receipt_telegram_file_id, receipt_local_path
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING id
            """,
            tx_type,
            decimal.Decimal(str(amount)),
            category,
            description,
            tx_date,
            receipt_telegram_file_id,
            receipt_local_path,
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
            SELECT TRIM(category) as category, SUM(amount) as total
            FROM finances
            WHERE EXTRACT(MONTH FROM tx_date) = $1 
              AND EXTRACT(YEAR FROM tx_date) = $2
              AND type = 'expense'
            GROUP BY TRIM(category)
            ORDER BY total DESC
            """,
            month,
            year,
        )
        return [dict(r) for r in rows]


async def get_budget_status(pool) -> List[Dict[str, Any]]:
    """Gets current weekly and monthly spending vs configured limits."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT 
                bl.category, 
                bl.monthly_limit,
                bl.weekly_limit,
                COALESCE((SELECT SUM(fm.amount) FROM finances fm
                    WHERE fm.type = 'expense'
                      AND (LOWER(fm.category) = LOWER(bl.category) OR LOWER(bl.category) IN ('total', 'general'))
                      AND fm.tx_date >= date_trunc('month', CURRENT_DATE)::date), 0) as monthly_spent,
                COALESCE((SELECT SUM(fw.amount) FROM finances fw
                    WHERE fw.type = 'expense'
                      AND (LOWER(fw.category) = LOWER(bl.category) OR LOWER(bl.category) IN ('total', 'general'))
                      AND fw.tx_date >= CURRENT_DATE - (EXTRACT(ISODOW FROM CURRENT_DATE)::integer - 1)), 0) as weekly_spent
            FROM budget_limits bl
            GROUP BY bl.category, bl.monthly_limit, bl.weekly_limit
            """
        )
        return [{**dict(r), "current_spent": r["monthly_spent"]} for r in rows]


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
        inc = float(row["income"])
        exp = float(row["expense"])
        return {"income": inc, "expense": exp, "balance": inc - exp}


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
async def set_budget_limit(pool, category: str, limit: float, period: str = "monthly"):
    """Sets or updates a weekly or monthly budget for a category."""
    async with pool.acquire() as conn:
        if period == "weekly":
            await conn.execute("""
                INSERT INTO budget_limits (category, monthly_limit, weekly_limit)
                VALUES ($1, 0, $2)
                ON CONFLICT (LOWER(category)) DO UPDATE SET weekly_limit = EXCLUDED.weekly_limit
            """, category, limit)
        else:
            await conn.execute("""
                INSERT INTO budget_limits (category, monthly_limit)
                VALUES ($1, $2)
                ON CONFLICT (LOWER(category)) DO UPDATE SET monthly_limit = EXCLUDED.monthly_limit
            """, category, limit)


async def get_category_transactions(pool, category: str, month: int, year: int) -> List[Dict[str, Any]]:
    """Returns all expense entries for one category in a calendar month."""
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT id, type, amount, category, description, tx_date AS transaction_date, created_at
            FROM finances
            WHERE type = 'expense' AND LOWER(TRIM(category)) = LOWER(TRIM($1))
              AND EXTRACT(MONTH FROM tx_date) = $2 AND EXTRACT(YEAR FROM tx_date) = $3
            ORDER BY tx_date DESC, created_at DESC
        """, category, month, year)
        return [dict(r) for r in rows]


async def reset_all_budget_alerts(pool) -> None:
    async with pool.acquire() as conn:
        await conn.execute("""UPDATE budget_limits SET alerted_80 = FALSE, alerted_100 = FALSE,
            alerted_weekly_80 = FALSE, alerted_weekly_100 = FALSE""")


async def reset_weekly_budget_alerts(pool) -> None:
    async with pool.acquire() as conn:
        await conn.execute("UPDATE budget_limits SET alerted_weekly_80 = FALSE, alerted_weekly_100 = FALSE")


async def claim_budget_alerts(pool) -> List[Dict[str, Any]]:
    """Atomically claims threshold alerts so Telegram sends each threshold once."""
    alerts: List[Dict[str, Any]] = []
    statuses = await get_budget_status(pool)
    async with pool.acquire() as conn:
        for row in statuses:
            category = row["category"]
            monthly_limit = float(row["monthly_limit"] or 0)
            weekly_limit = float(row["weekly_limit"] or 0)
            monthly_spent = float(row["monthly_spent"] or 0)
            weekly_spent = float(row["weekly_spent"] or 0)
            for period, spent, limit in (
                ("lunar", monthly_spent, monthly_limit),
                ("săptămânal", weekly_spent, weekly_limit),
            ):
                if not limit:
                    continue
                threshold = 100 if spent >= limit else 80 if spent >= limit * 0.8 else 0
                if not threshold:
                    continue
                if period == "lunar":
                    updated = await conn.fetchval(
                        "UPDATE budget_limits SET alerted_100 = CASE WHEN $2 = 100 THEN TRUE ELSE alerted_100 END, alerted_80 = CASE WHEN $2 = 80 THEN TRUE ELSE alerted_80 END WHERE LOWER(category) = LOWER($1) AND COALESCE(CASE WHEN $2 = 100 THEN alerted_100 ELSE alerted_80 END, FALSE) = FALSE RETURNING category",
                        category, threshold,
                    )
                else:
                    updated = await conn.fetchval(
                        "UPDATE budget_limits SET alerted_weekly_100 = CASE WHEN $2 = 100 THEN TRUE ELSE alerted_weekly_100 END, alerted_weekly_80 = CASE WHEN $2 = 80 THEN TRUE ELSE alerted_weekly_80 END WHERE LOWER(category) = LOWER($1) AND COALESCE(CASE WHEN $2 = 100 THEN alerted_weekly_100 ELSE alerted_weekly_80 END, FALSE) = FALSE RETURNING category",
                        category, threshold,
                    )
                if updated:
                    alerts.append({"category": category, "period": period, "spent": spent, "limit": limit, "threshold": threshold})
    return alerts


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
            SELECT id, type, amount, category, description, tx_date AS transaction_date, created_at
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


async def get_weekly_finance_summary(pool, start_date: date, end_date: date) -> Dict[str, float]:
    """Gets total expenses and income for a specific date range."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT 
                COALESCE(SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END), 0) as expense,
                COALESCE(SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END), 0) as income
            FROM finances
            WHERE tx_date BETWEEN $1 AND $2
            """,
            start_date,
            end_date,
        )
        exp = float(row["expense"])
        inc = float(row["income"])
        return {"total": exp, "expense": exp, "income": inc, "balance": inc - exp}
