"""Preserve every source table in a consistent, private snapshot before cutover."""

import hashlib
import json
import uuid
from typing import Any

import asyncpg


async def read_snapshot(source: asyncpg.Pool) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    async with source.acquire() as conn:
        async with conn.transaction(isolation="repeatable_read", readonly=True):
            tables = await conn.fetch(
                "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename"
            )
            for table in tables:
                # PostgreSQL quotes identifiers from its own catalog; values are
                # never interpolated. ORDER BY JSON also covers tables without PKs.
                query = await conn.fetchval(
                    "SELECT format('SELECT to_jsonb(t)::text AS payload FROM public.%I t ORDER BY to_jsonb(t)::text', $1::text)",
                    table["tablename"],
                )
                result[table["tablename"]] = [json.loads(r["payload"]) for r in await conn.fetch(query)]
    return result


async def save_snapshot(
    target: asyncpg.Pool, owner_id: int, data: dict[str, list[dict[str, Any]]],
) -> uuid.UUID:
    snapshot_id = uuid.uuid4()
    manifest = {table: len(rows) for table, rows in data.items()}
    async with target.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                "INSERT INTO legacy_snapshots(id,owner_id,manifest) VALUES ($1,$2,$3::jsonb)",
                snapshot_id, owner_id, json.dumps(manifest),
            )
            for table, rows in data.items():
                payload = json.dumps(rows, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
                digest = hashlib.sha256(payload.encode()).hexdigest()
                await conn.execute(
                    """INSERT INTO legacy_snapshot_tables(snapshot_id,table_name,row_count,sha256,rows)
                    VALUES ($1,$2,$3,$4,$5::jsonb)""",
                    snapshot_id, table, len(rows), digest, payload,
                )
                stored = json.loads(await conn.fetchval(
                    "SELECT rows::text FROM legacy_snapshot_tables WHERE snapshot_id=$1 AND table_name=$2",
                    snapshot_id, table,
                ))
                if stored != rows:
                    raise ValueError("Legacy snapshot verification failed: " + table)
    return snapshot_id
