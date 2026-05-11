from typing import List, Dict, Any, Optional


async def save_memory_fact(
    pool,
    user_id: int,
    category: str,
    fact: str,
    source: str,
    confidence: float = 1.0,
    expires_at: str = None,
    embedding: List[float] = None,
) -> int:
    """Saves a new memory fact to the database."""
    # Convert embedding to string for pgvector if it's a list
    embedding_str = str(embedding) if embedding else None
    
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO memory_facts (user_id, category, fact, source, confidence, expires_at, embedding)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING id
            """,
            user_id,
            category,
            fact,
            source,
            confidence,
            expires_at,
            embedding_str,
        )
        return row["id"]


async def save_auto_memory(
    pool,
    user_id: int,
    fact: str,
    category: str,
    confidence: float,
    expires_at: str = None,
) -> bool:
    """
    Saves a memory fact automatically, with deduplication.
    Checks for same category and similar start of fact (first 50 chars).
    """
    if confidence < 0.8 or not fact:
        return False

    prefix = fact[:50].strip().lower()

    async with pool.acquire() as conn:
        # Deduplication check
        existing = await conn.fetchval(
            """
            SELECT id FROM memory_facts 
            WHERE user_id = $1 AND category = $2 AND LOWER(fact) ILIKE $3
            LIMIT 1
            """,
            user_id,
            category,
            f"{prefix}%",
        )

        if existing:
            # Update last_seen and confidence if higher
            await conn.execute(
                """
                UPDATE memory_facts 
                SET last_seen = NOW(), confidence = GREATEST(confidence, $1), times_referenced = times_referenced + 1
                WHERE id = $2
                """,
                confidence,
                existing,
            )
            return False

        # New fact
        await conn.execute(
            """
            INSERT INTO memory_facts (user_id, category, fact, source, confidence, expires_at)
            VALUES ($1, $2, $3, 'auto', $4, $5)
            """,
            user_id,
            category,
            fact,
            confidence,
            expires_at,
        )
        return True


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

    # Clean keywords for tsquery: only alphanumeric and Romanian characters
    def clean_kw(k):
        return "".join(c for c in k if c.isalnum())

    valid_keywords = [clean_kw(k) for k in valid_keywords if clean_kw(k)]
    if not valid_keywords:
        return []

    search_query = " | ".join(valid_keywords)
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


async def semantic_search_memories(
    pool, user_id: int, query_embedding: List[float], limit: int = 5
) -> List[Dict[str, Any]]:
    """Searches memories using vector similarity (cosine distance)."""
    # Convert embedding to string for pgvector if it's a list
    emb_str = str(query_embedding) if query_embedding else None

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT *, 1 - (embedding <=> $2) as similarity
            FROM memory_facts
            WHERE user_id = $1 AND embedding IS NOT NULL
            ORDER BY similarity DESC
            LIMIT $3
            """,
            user_id,
            emb_str,
            limit,
        )
        return [dict(r) for r in rows]

async def get_random_memory_lane(pool) -> Optional[Dict[str, Any]]:
    """Gets a random fact from at least 7 days ago for 'Memory Lane'."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM memory_facts WHERE created_at < NOW() - INTERVAL '7 days' ORDER BY RANDOM() LIMIT 1"
        )
        return dict(row) if row else None
