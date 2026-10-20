"""One-way Apple Calendar projection for events created in Lora v2.

Legacy events and academic recurrences remain in their existing collection.
Remote edits are reported as conflicts instead of being overwritten.
"""

import asyncio
import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone

import asyncpg
import caldav
from icalendar import Alarm, Calendar, Event

from lora_v2.config import Settings


def _normalized(value: datetime) -> datetime:
    return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _revision(title: str, start: datetime, end: datetime, notes: str | None) -> str:
    payload = json.dumps([title, _normalized(start).isoformat(), _normalized(end).isoformat(), notes or ""],
                         ensure_ascii=False)
    return hashlib.sha256(payload.encode()).hexdigest()


def _snapshot(event: caldav.Event) -> tuple[str, str]:
    component = Calendar.from_ical(event.data).walk("VEVENT")[0]
    start = component["dtstart"].dt
    end_prop = component.get("dtend")
    end = end_prop.dt if end_prop else start + timedelta(hours=1)
    if not isinstance(start, datetime) or not isinstance(end, datetime):
        raise ValueError("All-day Apple event requires manual review")
    return str(component["uid"]), _revision(
        str(component.get("summary", "")), start, end,
        str(component.get("description", "")),
    )


def _event_data(event: caldav.Event) -> dict[str, object]:
    component = Calendar.from_ical(event.data).walk('VEVENT')[0]
    start = component['dtstart'].dt
    end_prop = component.get('dtend')
    end = end_prop.dt if end_prop else start + timedelta(hours=1)
    if not isinstance(start, datetime) or not isinstance(end, datetime):
        return {
            'title': str(component.get('summary', '')),
            'starts_at': str(start), 'ends_at': str(end),
            'notes': str(component.get('description', '')),
            'revision': hashlib.sha256(
                event.data.encode() if isinstance(event.data, str) else event.data
            ).hexdigest(),
            'unsupported': True,
        }
    return {
        'title': str(component.get('summary', '')),
        'starts_at': start,
        'ends_at': end,
        'notes': str(component.get('description', '')),
        'revision': _snapshot(event)[1],
    }


class AppleEventRemote:
    """Synchronous CalDAV calls run through asyncio.to_thread."""

    def __init__(self, settings: Settings):
        self.settings = settings

    def _collection(self) -> caldav.Calendar:
        if not self.settings.icloud_username or not self.settings.icloud_app_password:
            raise RuntimeError("iCloud credentials not configured")
        client = caldav.DAVClient(
            url="https://caldav.icloud.com", username=self.settings.icloud_username,
            password=self.settings.icloud_app_password,
        )
        principal = client.principal()
        for collection in principal.calendars():
            if collection.name == self.settings.apple_calendar_name:
                return collection
        return principal.make_calendar(
            name=self.settings.apple_calendar_name,
            supported_calendar_component_set=["VEVENT"],
        )

    @staticmethod
    def _find(collection: caldav.Calendar, uid: str) -> caldav.Event | None:
        for event in collection.events():
            component = Calendar.from_ical(event.data).walk('VEVENT')[0]
            if str(component.get('uid')) == uid:
                return event
        return None

    def get_snapshot(self, uid: str) -> dict[str, object] | None:
        event = self._find(self._collection(), uid)
        return _event_data(event) if event else None

    def get_revision(self, uid: str) -> str | None:
        snapshot = self.get_snapshot(uid)
        return str(snapshot['revision']) if snapshot else None

    def list_revisions(self) -> dict[str, str]:
        """Read the dedicated calendar once per reconciliation cycle."""
        revisions: dict[str, str] = {}
        for event in self._collection().events():
            component = Calendar.from_ical(event.data).walk('VEVENT')[0]
            uid = str(component.get('uid', ''))
            if uid.startswith('lora-v2-event-'):
                revisions[uid] = str(_event_data(event)['revision'])
        return revisions

    def upsert(
        self, uid: str, title: str, start: datetime, end: datetime,
        notes: str | None, alert_offsets: list[int],
    ) -> str:
        collection = self._collection()
        calendar = Calendar()
        calendar.add("prodid", "-//Lora v2//Calendar//RO")
        calendar.add("version", "2.0")
        event = Event()
        event.add("uid", uid)
        event.add("dtstamp", datetime.now(timezone.utc))
        event.add("summary", title)
        event.add("dtstart", start)
        event.add("dtend", end)
        if notes:
            event.add("description", notes)
        for offset in alert_offsets:
            alarm = Alarm()
            alarm.add("action", "DISPLAY")
            alarm.add("description", title)
            alarm.add("trigger", timedelta(minutes=-offset))
            event.add_component(alarm)
        calendar.add_component(event)
        remote = self._find(collection, uid)
        if remote:
            remote.data = calendar.to_ical().decode()
            remote.save()
        else:
            remote = collection.add_event(calendar.to_ical())
        return _snapshot(remote)[1]

    def delete(self, uid: str) -> None:
        remote = self._find(self._collection(), uid)
        if remote:
            remote.delete()


async def sync_events(pool: asyncpg.Pool, settings: Settings, owner_id: int) -> dict[str, int]:
    """Reconcile only v2-owned events, preserving remote edits for review."""
    if not settings.apple_events_enabled or not settings.icloud_username or not settings.icloud_app_password:
        return {"synced": 0, "conflicts": 0, "errors": 0}
    rows = await pool.fetch(
        """SELECT e.id,e.title,e.starts_at,e.ends_at,e.notes,e.status,e.version,
        l.apple_uid,l.apple_revision,l.last_synced_version
        FROM calendar_entries e LEFT JOIN apple_event_links l
        ON l.owner_id=e.owner_id AND l.entity_id=e.id
        WHERE e.owner_id=$1 AND e.kind='event' AND e.legacy_source IS NULL
        AND (e.starts_at >= now()-interval '1 day' OR l.entity_id IS NOT NULL)
        ORDER BY e.starts_at LIMIT 200""", owner_id,
    )
    remote = AppleEventRemote(settings)
    counts = {"synced": 0, "conflicts": 0, "errors": 0}
    try:
        remote_revisions = await asyncio.to_thread(remote.list_revisions)
    except Exception:
        return {"synced": 0, "conflicts": 0, "errors": len(rows) or 1}
    for row in rows:
        if row['status'] == 'cancelled' and not row['apple_uid']:
            continue
        uid = row['apple_uid'] or f"lora-v2-event-{row['id']}@lora"
        end = row['ends_at'] or row['starts_at'] + timedelta(hours=1)
        wanted = _revision(row['title'], row['starts_at'], end, row['notes'])
        try:
            current = remote_revisions.get(uid)
            if row['apple_uid'] and current == row['apple_revision'] and row['last_synced_version'] == row['version']:
                await pool.execute(
                    """UPDATE apple_event_conflicts SET status='resolved'
                    WHERE owner_id=$1 AND entity_id=$2 AND status='pending'""",
                    owner_id, row['id'],
                )
                continue
            if ((row['apple_uid'] and current != row['apple_revision'])
                    or (not row['apple_uid'] and current is not None and current != wanted)):
                await pool.execute(
                    """INSERT INTO apple_event_conflicts(owner_id,entity_id,apple_uid,
                    local_version,apple_revision) VALUES ($1,$2,$3,$4,$5)
                    ON CONFLICT(owner_id,entity_id) DO UPDATE SET
                    local_version=EXCLUDED.local_version,apple_revision=EXCLUDED.apple_revision,
                    status='pending'""",
                    owner_id, row['id'], uid, row['version'], current,
                )
                counts['conflicts'] += 1
                continue
            if row['status'] == 'cancelled':
                await asyncio.to_thread(remote.delete, uid)
                await pool.execute(
                    'DELETE FROM apple_event_links WHERE owner_id=$1 AND entity_id=$2',
                    owner_id, row['id'],
                )
            else:
                purposes = await pool.fetch(
                    """SELECT DISTINCT purpose FROM alert_occurrences
                    WHERE owner_id=$1 AND entry_id=$2 AND status!='cancelled'""",
                    owner_id, row['id'],
                )
                offsets = sorted({int(item['purpose'][7:-1]) for item in purposes
                                  if item['purpose'].startswith('before_')
                                  and item['purpose'].endswith('m')
                                  and item['purpose'][7:-1].isdigit()})
                revision = await asyncio.to_thread(remote.upsert, uid, row['title'],
                                                   row['starts_at'], end, row['notes'], offsets)
                remote_revisions[uid] = revision
                await pool.execute(
                    """INSERT INTO apple_event_links(owner_id,entity_id,apple_uid,apple_revision,last_synced_version)
                    VALUES ($1,$2,$3,$4,$5) ON CONFLICT(owner_id,entity_id) DO UPDATE SET
                    apple_revision=EXCLUDED.apple_revision,last_synced_version=EXCLUDED.last_synced_version,
                    updated_at=now()""",
                    owner_id, row['id'], uid, revision, row['version'],
                )
            await pool.execute(
                """UPDATE apple_event_conflicts SET status='resolved'
                WHERE owner_id=$1 AND entity_id=$2 AND status='pending'""",
                owner_id, row['id'],
            )
            counts['synced'] += 1
        except Exception:
            counts['errors'] += 1
    return counts


async def resolve_event_conflict(
    pool: asyncpg.Pool, settings: Settings, owner_id: int,
    entity_id: uuid.UUID, choice: str, expected_version: int,
) -> str:
    """Resolve a reviewed event conflict without modifying unrelated calendars."""
    if choice not in {'keep_lora', 'use_apple'}:
        raise ValueError('Alegere necunoscută.')
    conflict = await pool.fetchrow(
        """SELECT apple_uid,apple_revision,local_version,status FROM apple_event_conflicts
        WHERE owner_id=$1 AND entity_id=$2""", owner_id, entity_id,
    )
    if not conflict or conflict['status'] != 'pending' or conflict['local_version'] != expected_version:
        raise ValueError('Conflictul s-a schimbat. Reîncarcă înainte de alegere.')
    remote = await asyncio.to_thread(AppleEventRemote(settings).get_snapshot, conflict['apple_uid'])
    current_revision = str(remote['revision']) if remote else None
    if current_revision != conflict['apple_revision']:
        raise ValueError('Evenimentul Apple a fost modificat. Reîncarcă înainte de alegere.')
    async with pool.acquire() as conn:
        async with conn.transaction():
            local = await conn.fetchrow(
                """SELECT id,status,starts_at,version FROM calendar_entries
                WHERE id=$1 AND owner_id=$2 AND kind='event' AND legacy_source IS NULL FOR UPDATE""",
                entity_id, owner_id,
            )
            current_conflict = await conn.fetchrow(
                """SELECT local_version,status FROM apple_event_conflicts
                WHERE owner_id=$1 AND entity_id=$2 FOR UPDATE""", owner_id, entity_id,
            )
            if (not local or local['version'] != expected_version or not current_conflict
                    or current_conflict['status'] != 'pending'
                    or current_conflict['local_version'] != expected_version):
                raise ValueError('Conflictul s-a schimbat. Reîncarcă înainte de alegere.')
            if choice == 'keep_lora':
                if current_revision is None:
                    await conn.execute(
                        'DELETE FROM apple_event_links WHERE owner_id=$1 AND entity_id=$2',
                        owner_id, entity_id,
                    )
                else:
                    await conn.execute(
                        """INSERT INTO apple_event_links(owner_id,entity_id,apple_uid,
                        apple_revision,last_synced_version) VALUES ($1,$2,$3,$4,0)
                        ON CONFLICT(owner_id,entity_id) DO UPDATE SET
                        apple_revision=EXCLUDED.apple_revision,last_synced_version=0,
                        updated_at=now()""",
                        owner_id, entity_id, conflict['apple_uid'], current_revision,
                    )
                message = 'Versiunea Lora va fi trimisă în Apple Calendar.'
            elif remote is None:
                await conn.execute(
                    """UPDATE calendar_entries SET status='cancelled',version=version+1,
                    updated_at=now() WHERE id=$1 AND owner_id=$2""", entity_id, owner_id,
                )
                await conn.execute(
                    """UPDATE alert_occurrences SET status='cancelled' WHERE entry_id=$1
                    AND owner_id=$2 AND status='pending'""", entity_id, owner_id,
                )
                await conn.execute(
                    'DELETE FROM apple_event_links WHERE owner_id=$1 AND entity_id=$2',
                    owner_id, entity_id,
                )
                message = 'Ștergerea din Apple Calendar a fost preluată în Lora.'
            else:
                starts_at = remote['starts_at']
                ends_at = remote['ends_at']
                if not isinstance(starts_at, datetime) or not isinstance(ends_at, datetime):
                    raise ValueError('Formatul evenimentului Apple nu este acceptat.')
                await conn.execute(
                    """UPDATE calendar_entries SET title=$3,starts_at=$4,ends_at=$5,notes=$6,
                    status='active',version=version+1,updated_at=now()
                    WHERE id=$1 AND owner_id=$2""",
                    entity_id, owner_id, str(remote['title']), starts_at, ends_at,
                    str(remote['notes']) or None,
                )
                purposes = await conn.fetch(
                    'SELECT DISTINCT purpose FROM alert_occurrences WHERE owner_id=$1 AND entry_id=$2',
                    owner_id, entity_id,
                )
                await conn.execute(
                    """UPDATE alert_occurrences SET status='cancelled'
                    WHERE owner_id=$1 AND entry_id=$2 AND status='pending'""",
                    owner_id, entity_id,
                )
                for item in purposes:
                    purpose = item['purpose']
                    if purpose.startswith('before_') and purpose.endswith('m') and purpose[7:-1].isdigit():
                        alert_at = starts_at - timedelta(minutes=int(purpose[7:-1]))
                        if alert_at > datetime.now(timezone.utc):
                            await conn.execute(
                                """INSERT INTO alert_occurrences(id,owner_id,entry_id,alert_at,purpose)
                                VALUES ($1,$2,$3,$4,$5) ON CONFLICT DO NOTHING""",
                                uuid.uuid4(), owner_id, entity_id, alert_at, purpose,
                            )
                await conn.execute(
                    """INSERT INTO apple_event_links(owner_id,entity_id,apple_uid,
                    apple_revision,last_synced_version) VALUES ($1,$2,$3,$4,$5)
                    ON CONFLICT(owner_id,entity_id) DO UPDATE SET
                    apple_revision=EXCLUDED.apple_revision,
                    last_synced_version=EXCLUDED.last_synced_version,updated_at=now()""",
                    owner_id, entity_id, conflict['apple_uid'], current_revision,
                    expected_version + 1,
                )
                message = 'Versiunea Apple Calendar a fost preluată în Lora.'
            await conn.execute(
                """UPDATE apple_event_conflicts SET status='resolved'
                WHERE owner_id=$1 AND entity_id=$2""", owner_id, entity_id,
            )
    return message
