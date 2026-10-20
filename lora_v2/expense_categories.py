"""Use the owner's active categories as evidence, never as a forced guess."""

import re
import unicodedata

import asyncpg


def _plain(text: str) -> str:
    normalized = unicodedata.normalize('NFD', text.casefold())
    return ''.join(char for char in normalized if unicodedata.category(char) != 'Mn')


async def category_context(pool: asyncpg.Pool, owner_id: int) -> str:
    rows = await pool.fetch(
        "SELECT name FROM expense_categories WHERE owner_id=$1 AND is_active=true ORDER BY name",
        owner_id,
    )
    return ', '.join(row['name'] for row in rows)


async def category_hint(pool: asyncpg.Pool, owner_id: int, text: str) -> str | None:
    """Return a category only for one unambiguous keyword match."""
    rows = await pool.fetch(
        """SELECT name,keywords FROM expense_categories
        WHERE owner_id=$1 AND is_active=true""", owner_id,
    )
    source = _plain(text)
    matches = set()
    for row in rows:
        for keyword in row['keywords'] or []:
            key = _plain(keyword.strip())
            if len(key) >= 4 and re.search(r'(?<!\w)' + re.escape(key) + r'(?!\w)', source):
                matches.add(row['name'])
                break
    return next(iter(matches)) if len(matches) == 1 else None


async def canonical_category(pool: asyncpg.Pool, owner_id: int, category: str) -> str:
    rows = await pool.fetch(
        "SELECT name FROM expense_categories WHERE owner_id=$1 AND is_active=true", owner_id,
    )
    return next((row['name'] for row in rows if _plain(row['name']) == _plain(category)), category)
