"""Non-destructive Obsidian -> Lora synchronization for calendar data."""

from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Any

from integrations.obsidian_sync import VAULT_PATH

logger = logging.getLogger("lora.obsidian.bidirectional")


def _frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return {}
    block = text.split("\n---", 1)[0][4:]
    result: dict[str, str] = {}
    for line in block.splitlines():
        match = re.match(r"^([A-Za-z0-9_]+):\s*(.*)$", line)
        if match:
            value = match.group(2).strip().strip('"')
            result[match.group(1)] = value
    return result


def _date(value: str) -> date:
    return date.fromisoformat(value)


def _time(value: str) -> time:
    return time.fromisoformat(value)


def _file_time(path: Path) -> datetime:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)


async def _audit(conn: Any, entity_type: str, entity_id: str, operation: str, source_time: datetime, payload: dict[str, Any]) -> None:
    await conn.execute(
        """INSERT INTO obsidian_sync_audit
           (entity_type, entity_id, source, operation, source_updated_at, payload)
           VALUES ($1, $2, 'obsidian', $3, $4, $5::jsonb)""",
        entity_type, entity_id, operation, source_time, json.dumps(payload, default=str, ensure_ascii=False),
    )


async def sync_calendar_from_obsidian(pool) -> dict[str, int]:
    """Import changed schedule/academic-period notes without destructive deletes."""
    stats = {"updated": 0, "skipped": 0, "conflicts": 0, "errors": 0}
    roots = (("schedule", VAULT_PATH / "06 Calendar" / "_Schedule"), ("academic_period", VAULT_PATH / "06 Calendar" / "_Academic Periods"))
    async with pool.acquire() as conn:
        for entity_type, root in roots:
            if not root.is_dir():
                continue
            for path in root.glob("*.md"):
                try:
                    meta = _frontmatter(path)
                    if meta.get("type") != entity_type or not meta.get("lora_id"):
                        stats["skipped"] += 1
                        continue
                    entity_id = int(meta["lora_id"])
                    source_time = _file_time(path)
                    if entity_type == "schedule":
                        row = await conn.fetchrow("SELECT created_at FROM schedule WHERE id = $1", entity_id)
                        if not row or source_time <= row["created_at"].replace(tzinfo=timezone.utc):
                            stats["skipped"] += 1
                            continue
                        payload = {k: meta.get(k) for k in ("day_of_week", "start_time", "end_time", "room", "class_type", "week_type")}
                        await _audit(conn, entity_type, str(entity_id), "update", source_time, payload)
                        await conn.execute("""UPDATE schedule SET day_of_week=$1, start_time=$2, end_time=$3,
                            room=$4, class_type=$5, week_type=$6 WHERE id=$7""",
                            int(payload["day_of_week"]), _time(payload["start_time"]), _time(payload["end_time"]),
                            payload["room"] or None, payload["class_type"] or "curs", payload["week_type"] or "both", entity_id)
                    else:
                        row = await conn.fetchrow("SELECT created_at FROM academic_periods WHERE id = $1", entity_id)
                        if not row or source_time <= row["created_at"].replace(tzinfo=timezone.utc):
                            stats["skipped"] += 1
                            continue
                        payload = {k: meta.get(k) for k in ("academic_year", "semester", "period_type", "start_date", "end_date", "description")}
                        await _audit(conn, entity_type, str(entity_id), "update", source_time, payload)
                        await conn.execute("""UPDATE academic_periods SET academic_year=$1, semester=$2,
                            period_type=$3, start_date=$4, end_date=$5, description=$6 WHERE id=$7""",
                            payload["academic_year"], int(payload["semester"]), payload["period_type"],
                            _date(payload["start_date"]), _date(payload["end_date"]), payload["description"], entity_id)
                    stats["updated"] += 1
                except Exception:
                    stats["errors"] += 1
                    logger.exception("Obsidian calendar import failed for %s", path)
    return stats
