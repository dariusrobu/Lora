from typing import Optional, Dict, Any


async def get_sync_record(
    pool, lora_type: str, lora_id: int
) -> Optional[Dict[str, Any]]:
    """Checks if a Lora item has already been synced to iCloud."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM calendar_sync WHERE lora_type = $1 AND lora_id = $2",
            lora_type,
            lora_id,
        )
        return dict(row) if row else None


async def get_sync_record_by_uid(pool, ical_uid: str) -> Optional[Dict[str, Any]]:
    """Checks for a sync record by its iCloud UID."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM calendar_sync WHERE ical_uid = $1", ical_uid
        )
        return dict(row) if row else None


async def save_sync_record(
    pool, lora_type: str, lora_id: int, ical_uid: str, summary: str
):
    """Saves or updates a synchronization record."""
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO calendar_sync (lora_type, lora_id, ical_uid, summary, synced_at)
            VALUES ($1, $2, $3, $4, NOW())
            ON CONFLICT (ical_uid) DO UPDATE 
            SET summary = EXCLUDED.summary, last_modified = NOW()
            """,
            lora_type,
            lora_id,
            ical_uid,
            summary,
        )


async def delete_sync_record(pool, ical_uid: str):
    """Removes a sync record."""
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM calendar_sync WHERE ical_uid = $1", ical_uid)
