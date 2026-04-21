import re
from typing import List, Dict, Any


async def save_memory_fact(
    pool, category: str, fact: str, source: str, confidence: float = 1.0
) -> int:
    """Saves a new memory fact to the database.

    Args:
        pool: Database connection pool.
        category: 'preference', 'pattern', 'personal', 'achievement'.
        fact: The extracted fact.
        source: 'user_stated', 'inferred', 'observed'.
        confidence: Confidence score (0.0 to 1.0).

    Returns:
        The ID of the newly created fact.
    """
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO memory_facts (category, fact, source, confidence)
            VALUES ($1, $2, $3, $4)
            RETURNING id
            """,
            category,
            fact,
            source,
            confidence,
        )
        return row["id"]


async def get_relevant_facts(pool, query_keywords: List[str]) -> List[Dict[str, Any]]:
    """Retrieves facts relevant to the given keywords using full-text search.
    OPTIMIZED: Uses rank-based ordering.
    """
    if not query_keywords:
        return []

    # Filter out very short words and join with OR
    valid_keywords = [k for k in query_keywords if len(k) >= 3]
    if not valid_keywords:
        return []

    search_query = " | ".join(re.escape(k) for k in valid_keywords)
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT *, ts_rank(to_tsvector('simple', fact), to_tsquery('simple', $1)) as rank
            FROM memory_facts
            WHERE to_tsvector('simple', fact) @@ to_tsquery('simple', $1)
            ORDER BY rank DESC, times_referenced DESC
            LIMIT 5
            """,
            search_query,
        )
        return [dict(r) for r in rows]


async def get_all_facts_by_category(pool, category: str) -> List[Dict[str, Any]]:
    """Retrieves all facts in a specific category.

    Args:
        pool: Database connection pool.
        category: The category to filter by.

    Returns:
        A list of facts.
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM memory_facts WHERE category = $1 ORDER BY created_at DESC",
            category,
        )
        return [dict(r) for r in rows]


async def update_fact_seen(pool, fact_id: int) -> None:
    """Updates the last_seen timestamp and increments the reference counter.

    Args:
        pool: Database connection pool.
        fact_id: The ID of the fact to update.
    """
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE memory_facts
            SET last_seen = NOW(), times_referenced = times_referenced + 1
            WHERE id = $1
            """,
            fact_id,
        )


async def delete_fact(pool, fact_id: int) -> None:
    """Deletes a fact by its ID.

    Args:
        pool: Database connection pool.
        fact_id: The ID of the fact to delete.
    """
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM memory_facts WHERE id = $1", fact_id)


async def delete_last_fact(pool):
    """Delete the most recently added fact."""
    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM memory_facts WHERE id = (SELECT id FROM memory_facts ORDER BY id DESC LIMIT 1)"
        )


async def clear_all_memories(pool):
    """Delete all facts from memory."""
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM memory_facts")


async def list_all_memories(pool) -> List[Dict[str, Any]]:
    """Lists all stored memories, ordered by category and date.

    Args:
        pool: Database connection pool.

    Returns:
        A list of all memory rows.
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM memory_facts ORDER BY category, created_at DESC"
        )
        return [dict(r) for r in rows]


async def search_memories(pool, query: str) -> List[Dict[str, Any]]:
    """Searches memories using ILIKE for specific text.

    Args:
        pool: Database connection pool.
        query: The string to search for.

    Returns:
        A list of matching memories.
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM memory_facts WHERE fact ILIKE $1", f"%{query}%"
        )
        return [dict(r) for r in rows]
