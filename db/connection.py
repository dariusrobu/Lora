import asyncpg
import logging
from pathlib import Path
from core.config import DATABASE_URL

_pool = None
logger = logging.getLogger("db.connection")

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


async def get_pool():
    global _pool
    if _pool is None:
        try:
            _pool = await asyncpg.create_pool(
                DATABASE_URL,
                min_size=0,
                max_size=20,
                max_inactive_connection_lifetime=60.0,
                command_timeout=30,
                server_settings={"application_name": "lora"},
            )
        except Exception as e:
            print(f"Error creating connection pool: {e}")
            raise
    return _pool


async def close_pool():
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


async def apply_migrations(pool=None) -> int:
    """
    Applies pending SQL migration files from db/migrations/ in alphabetical order.
    Tracks applied migrations in `schema_migrations` table (idempotent — safe to call on every startup).
    Returns the number of newly applied migrations.
    """
    if pool is None:
        pool = await get_pool()

    async with pool.acquire() as conn:
        # 1. Ensure tracking table exists
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version     TEXT PRIMARY KEY,
                filename    TEXT NOT NULL,
                applied_at  TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        # 2. Get already-applied migrations
        applied = {row["version"] for row in await conn.fetch("SELECT version FROM schema_migrations")}

        # 3. Collect & sort migration files (only .sql, alphabetical order)
        if not MIGRATIONS_DIR.exists():
            logger.warning(f"Migrations directory not found: {MIGRATIONS_DIR}")
            return 0

        migration_files = sorted(
            f for f in MIGRATIONS_DIR.iterdir()
            if f.suffix == ".sql"
        )

        applied_count = 0
        for mfile in migration_files:
            version = mfile.stem  # filename without .sql extension
            if version in applied:
                continue  # Already applied, skip

            logger.info(f"Applying migration: {mfile.name}")
            sql = mfile.read_text(encoding="utf-8")
            try:
                await conn.execute(sql)
                await conn.execute(
                    "INSERT INTO schema_migrations (version, filename) VALUES ($1, $2)",
                    version, mfile.name
                )
                applied_count += 1
                logger.info(f"✅ Migration applied: {mfile.name}")
            except Exception as e:
                logger.exception("Migration failed: %s", mfile.name)
                raise RuntimeError(f"Database migration failed: {mfile.name}") from e

    if applied_count > 0:
        logger.info(f"✅ Applied {applied_count} new migration(s).")
    else:
        logger.info("✅ Database schema is up to date (no new migrations).")
    return applied_count
