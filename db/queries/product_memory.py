import logging
import re
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


async def init_product_memory_table(pool) -> None:
    """Initializes persistent tables for learned receipt products and merchants."""
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS receipt_product_memory (
                id SERIAL PRIMARY KEY,
                raw_pattern TEXT NOT NULL,
                clean_name TEXT NOT NULL,
                category TEXT NOT NULL,
                merchant TEXT,
                frequency INT DEFAULT 1,
                last_price NUMERIC(10, 2),
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW(),
                UNIQUE(raw_pattern, merchant)
            );

            CREATE INDEX IF NOT EXISTS idx_receipt_product_pattern 
            ON receipt_product_memory(raw_pattern);

            CREATE TABLE IF NOT EXISTS receipt_merchant_memory (
                id SERIAL PRIMARY KEY,
                raw_pattern TEXT NOT NULL UNIQUE,
                clean_name TEXT NOT NULL,
                frequency INT DEFAULT 1,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            );

            CREATE INDEX IF NOT EXISTS idx_receipt_merchant_pattern 
            ON receipt_merchant_memory(raw_pattern);
        """)
        logger.info("✅ Persistent receipt product and merchant memory tables initialized.")


def _clean_pattern(text: str) -> str:
    """Normalizes raw text pattern for fuzzy or substring matching."""
    s = text.lower().strip()
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


async def remember_product(
    pool,
    raw_pattern: str,
    clean_name: str,
    category: str,
    merchant: Optional[str] = None,
    price: Optional[float] = None,
) -> None:
    """Saves or updates a confirmed product mapping."""
    if not pool or not hasattr(pool, "acquire") or "Mock" in type(pool).__name__:
        return

    norm_pattern = _clean_pattern(raw_pattern)
    norm_merchant = merchant.strip() if merchant else None

    if not norm_pattern or len(norm_pattern) < 3:
        return

    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO receipt_product_memory 
                (raw_pattern, clean_name, category, merchant, frequency, last_price, updated_at)
            VALUES ($1, $2, $3, $4, 1, $5, NOW())
            ON CONFLICT (raw_pattern, merchant) 
            DO UPDATE SET 
                clean_name = EXCLUDED.clean_name,
                category = EXCLUDED.category,
                frequency = receipt_product_memory.frequency + 1,
                last_price = COALESCE(EXCLUDED.last_price, receipt_product_memory.last_price),
                updated_at = NOW()
            """,
            norm_pattern,
            clean_name.strip(),
            category.strip().lower(),
            norm_merchant,
            price,
        )
    logger.info(f"🧠 Remembered product mapping: '{norm_pattern}' -> '{clean_name}' ({category})")


async def find_remembered_product(
    pool, text: str, merchant: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Looks up if any known product pattern matches the given item text."""
    if not pool or not hasattr(pool, "acquire") or "Mock" in type(pool).__name__:
        return None

    if not text or len(text.strip()) < 3:
        return None

    norm_text = _clean_pattern(text)
    norm_merchant = merchant.strip() if merchant else None

    async with pool.acquire() as conn:
        # 1. Exact or merchant-specific match first
        if norm_merchant:
            row = await conn.fetchrow(
                """
                SELECT clean_name, category, last_price, raw_pattern 
                FROM receipt_product_memory
                WHERE merchant = $1 AND ($2 ILIKE '%' || raw_pattern || '%' OR raw_pattern ILIKE '%' || $2 || '%')
                ORDER BY frequency DESC, LENGTH(raw_pattern) DESC
                LIMIT 1
                """,
                norm_merchant,
                norm_text,
            )
            if row:
                return dict(row)

        # 2. General global match
        row = await conn.fetchrow(
            """
            SELECT clean_name, category, last_price, raw_pattern 
            FROM receipt_product_memory
            WHERE ($1 ILIKE '%' || raw_pattern || '%' OR raw_pattern ILIKE '%' || $1 || '%')
            ORDER BY frequency DESC, LENGTH(raw_pattern) DESC
            LIMIT 1
            """,
            norm_text,
        )
        if row:
            return dict(row)

    return None


async def remember_merchant(pool, raw_pattern: str, clean_name: str) -> None:
    """Saves or updates a recognized merchant pattern."""
    if not pool or not hasattr(pool, "acquire") or "Mock" in type(pool).__name__:
        return

    norm_pattern = _clean_pattern(raw_pattern)
    if not norm_pattern or len(norm_pattern) < 3:
        return

    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO receipt_merchant_memory (raw_pattern, clean_name, frequency, updated_at)
            VALUES ($1, $2, 1, NOW())
            ON CONFLICT (raw_pattern)
            DO UPDATE SET 
                clean_name = EXCLUDED.clean_name,
                frequency = receipt_merchant_memory.frequency + 1,
                updated_at = NOW()
            """,
            norm_pattern,
            clean_name.strip(),
        )
    logger.info(f"🧠 Remembered merchant mapping: '{norm_pattern}' -> '{clean_name}'")


async def find_remembered_merchant(pool, ocr_text: str) -> Optional[str]:
    """Finds known merchant pattern inside the full receipt OCR text."""
    if not pool or not hasattr(pool, "acquire") or "Mock" in type(pool).__name__:
        return None

    if not ocr_text:
        return None

    norm_ocr = _clean_pattern(ocr_text)

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT raw_pattern, clean_name 
            FROM receipt_merchant_memory 
            ORDER BY frequency DESC, LENGTH(raw_pattern) DESC
            """
        )
        for r in rows:
            pattern = r["raw_pattern"]
            if pattern in norm_ocr:
                return r["clean_name"]

    return None


async def seed_default_memories(pool) -> None:
    """Seeds foundational supermarket and receipt memories."""
    defaults = [
        ("camelion baterie", "Baterie Camelion CR2032", "utilități", None, 3.40),
        ("baterie or2032", "Baterie Camelion CR2032", "utilități", None, 3.40),
        ("ursus premium", "Bere Ursus Premium 0.5L", "mâncare", None, 3.00),
        ("garantie sticla", "Garanție sticlă", "altele", None, 4.50),
        ("aro otet", "Oțet Aro 9 grade 1L", "mâncare", None, 6.00),
        ("dsc ing vanizm", "Desert înghețată vanilie", "mâncare", None, 4.99),
        ("vuse caps blueberry", "Vuse Caps Blueberry", "țigări", None, 20.50),
        ("cidru de nere", "Cidru de mere / pere", "mâncare", "IKEA", 4.50),
        ("cidru de mere", "Cidru de mere / pere", "mâncare", "IKEA", 4.50),
        ("aa plata ninerala", "Apă plată / minerală", "mâncare", "IKEA", 2.00),
        ("apa plata ninerala", "Apă plată / minerală", "mâncare", "IKEA", 2.00),
        ("euro luk 95", "Benzină Euro Luk 95", "transport", "Lukoil", 105.02),
        ("euro luk", "Benzină Euro Luk 95", "transport", "Lukoil", 105.02),
    ]
    for raw, clean, cat, merch, price in defaults:
        await remember_product(pool, raw, clean, cat, merch, price)

    merchants = [
        ("se feral imps sal", "SC FERAL IMPEX SRL"),
        ("feral impex", "SC FERAL IMPEX SRL"),
        ("ikea romania", "IKEA România"),
        ("descarca profi app", "Profi"),
        ("profi rom food", "Profi"),
        ("kaufland romania", "Kaufland"),
        ("lidl discount", "Lidl"),
        ("mega image srl", "Mega Image"),
        ("lukoil", "Lukoil"),
        ("omv petrom", "OMV Petrom"),
        ("omv romania", "OMV"),
        ("petrom", "Petrom"),
        ("rompetrol down", "Rompetrol"),
        ("mol romania", "MOL"),
    ]
    for raw_m, clean_m in merchants:
        await remember_merchant(pool, raw_m, clean_m)


async def list_product_memories(pool) -> list[dict[str, Any]]:
    """Lists all remembered product mappings ordered by frequency and clean_name."""
    if not pool or not hasattr(pool, "acquire"):
        return []
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, raw_pattern, clean_name, category, merchant, frequency, last_price, updated_at
            FROM receipt_product_memory
            ORDER BY frequency DESC, clean_name ASC
            LIMIT 150
            """
        )
        return [dict(r) for r in rows]


async def delete_product_memory(pool, item_id: int) -> bool:
    """Deletes a remembered product mapping by id."""
    if not pool or not hasattr(pool, "acquire"):
        return False
    async with pool.acquire() as conn:
        res = await conn.execute(
            "DELETE FROM receipt_product_memory WHERE id = $1", item_id
        )
        return res != "DELETE 0"


async def list_merchant_memories(pool) -> list[dict[str, Any]]:
    """Lists all remembered merchant mappings ordered by frequency."""
    if not pool or not hasattr(pool, "acquire"):
        return []
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, raw_pattern, clean_name, frequency, updated_at
            FROM receipt_merchant_memory
            ORDER BY frequency DESC, clean_name ASC
            LIMIT 100
            """
        )
        return [dict(r) for r in rows]


async def delete_merchant_memory(pool, item_id: int) -> bool:
    """Deletes a remembered merchant mapping by id."""
    if not pool or not hasattr(pool, "acquire"):
        return False
    async with pool.acquire() as conn:
        res = await conn.execute(
            "DELETE FROM receipt_merchant_memory WHERE id = $1", item_id
        )
        return res != "DELETE 0"
