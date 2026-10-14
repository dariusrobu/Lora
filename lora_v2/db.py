"""Separate PostgreSQL connection and checked migrations for Lora v2."""

import hashlib
from pathlib import Path

import asyncpg

from lora_v2.config import Settings

MIGRATIONS = Path(__file__).parent / "migrations"


async def create_pool(settings: Settings) -> asyncpg.Pool:
    return await asyncpg.create_pool(
        settings.database_url,
        min_size=1,
        max_size=10,
        command_timeout=30,
        server_settings={"application_name": "lora_v2"},
    )


async def migrate(pool: asyncpg.Pool) -> int:
    """Apply each migration atomically and reject modified applied files."""
    applied_count = 0
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                filename TEXT PRIMARY KEY,
                checksum TEXT NOT NULL,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
        """)
        for path in sorted(MIGRATIONS.glob("*.sql")):
            source = path.read_text(encoding="utf-8")
            checksum = hashlib.sha256(source.encode()).hexdigest()
            async with conn.transaction():
                await conn.execute("SELECT pg_advisory_xact_lock(12498276)")
                row = await conn.fetchrow(
                    "SELECT checksum FROM schema_migrations WHERE filename=$1", path.name
                )
                if row:
                    if row["checksum"] != checksum:
                        raise RuntimeError(f"Applied migration changed: {path.name}")
                    continue
                await conn.execute(source)
                await conn.execute(
                    "INSERT INTO schema_migrations(filename, checksum) VALUES ($1, $2)",
                    path.name, checksum,
                )
                applied_count += 1
    return applied_count
