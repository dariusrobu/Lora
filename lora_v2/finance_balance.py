"""Current RON balance anchored to an owner-confirmed amount."""

from decimal import Decimal
from typing import Any

import asyncpg


async def read_balance(pool: asyncpg.Pool, owner_id: int) -> dict[str, Any]:
    """Never present an incomplete historical ledger as the current balance."""
    async with pool.acquire() as conn:
        baseline = await conn.fetchrow(
            """SELECT b.amount,b.as_of,b.version,
                (SELECT COALESCE(SUM(i.amount),0) FROM incomes i
                 WHERE i.owner_id=b.owner_id AND i.currency='RON' AND i.deleted_at IS NULL
                 AND i.received_at > b.as_of AND i.received_at <= now()) AS income,
                (SELECT COALESCE(SUM(e.amount),0) FROM expenses e
                 WHERE e.owner_id=b.owner_id AND e.currency='RON' AND e.deleted_at IS NULL
                 AND e.spent_at > b.as_of AND e.spent_at <= now()) AS expenses
            FROM finance_balance_baselines b WHERE b.owner_id=$1 AND b.currency='RON'""",
            owner_id,
        )
        if baseline is None:
            return {"currency": "RON", "balance": None, "baseline": None,
                    "as_of": None, "version": None}
    balance = baseline["amount"] + baseline["income"] - baseline["expenses"]
    return {"currency": "RON", "balance": balance, "baseline": baseline["amount"],
            "as_of": baseline["as_of"], "version": baseline["version"]}


async def set_balance(pool: asyncpg.Pool, owner_id: int, amount: Decimal,
                      expected_version: int | None) -> dict[str, Any]:
    """Set the verified balance at the server's current time, with optimistic locking."""
    async with pool.acquire() as conn:
        if expected_version is None:
            row = await conn.fetchrow(
                """INSERT INTO finance_balance_baselines(owner_id,currency,amount,as_of)
                VALUES ($1,'RON',$2,now()) ON CONFLICT DO NOTHING
                RETURNING amount,as_of,version""", owner_id, amount,
            )
        else:
            row = await conn.fetchrow(
                """UPDATE finance_balance_baselines
                SET amount=$3,as_of=now(),version=version+1,updated_at=now()
                WHERE owner_id=$1 AND currency='RON' AND version=$2
                RETURNING amount,as_of,version""", owner_id, expected_version, amount,
            )
    if row is None:
        raise ValueError("Soldul a fost modificat între timp. Reîncarcă și încearcă din nou.")
    return {"currency": "RON", "balance": row["amount"], "baseline": row["amount"],
            "as_of": row["as_of"], "version": row["version"]}


async def clear_balance(pool: asyncpg.Pool, owner_id: int, expected_version: int) -> None:
    async with pool.acquire() as conn:
        deleted = await conn.execute(
            """DELETE FROM finance_balance_baselines
            WHERE owner_id=$1 AND currency='RON' AND version=$2""",
            owner_id, expected_version,
        )
    if deleted != "DELETE 1":
        raise ValueError("Soldul a fost modificat între timp. Reîncarcă și încearcă din nou.")
