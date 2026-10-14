"""Dedicated Apple Reminders list with UID mapping and two-way reconciliation."""

import asyncio
import hashlib
import json
import uuid
from datetime import date, datetime, time, timedelta, timezone
from typing import Literal
from zoneinfo import ZoneInfo

import asyncpg
import caldav
from icalendar import Alarm, Calendar, Todo

from lora_v2.config import Settings


def _as_datetime(value: date | datetime | None, tz: ZoneInfo) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=tz) if value.tzinfo is None else value.astimezone(tz)
    return datetime.combine(value, time(9, 0), tz)


def _snapshot(todo: caldav.Todo) -> tuple[str, str, datetime | None, bool]:
    component = Calendar.from_ical(todo.data).walk("VTODO")[0]
    uid = str(component.get("uid"))
    title = str(component.get("summary", ""))
    due_prop = component.get("due")
    due = _as_datetime(due_prop.dt, ZoneInfo("Europe/Bucharest")) if due_prop else None
    completed = str(component.get("status", "")).upper() == "COMPLETED" or bool(component.get("completed"))
    revision = _digest(title, due, completed)
    return uid, revision, due, completed


def _digest(title: str, due: datetime | None, completed: bool) -> str:
    local_due = due.astimezone(ZoneInfo("Europe/Bucharest")) if due else None
    return hashlib.sha256(
        f"{title}|{local_due.isoformat() if local_due else ''}|{completed}".encode()
    ).hexdigest()


class AppleRemote:
    """Synchronous CalDAV boundary; callers run these methods in a worker thread."""

    def __init__(self, settings: Settings):
        self.settings = settings

    def _list(self, create: bool = False) -> caldav.Calendar | None:
        if not self.settings.icloud_username or not self.settings.icloud_app_password:
            raise RuntimeError("iCloud credentials not configured")
        client = caldav.DAVClient(
            url="https://caldav.icloud.com",
            username=self.settings.icloud_username,
            password=self.settings.icloud_app_password,
        )
        principal = client.principal()
        for collection in principal.calendars():
            if collection.name == self.settings.apple_reminders_list:
                return collection
        if not create:
            return None
        return principal.make_calendar(
            name=self.settings.apple_reminders_list,
            supported_calendar_component_set=["VTODO"],
        )

    @staticmethod
    def _find_todo(collection: caldav.Calendar, uid: str) -> caldav.Todo | None:
        # iCloud can reject UID-filtered CalDAV REPORT requests with 412 even
        # while an unfiltered VTODO listing works. Match the UID locally.
        for todo in collection.todos(include_completed=True):
            if _snapshot(todo)[0] == uid:
                return todo
        return None

    def upsert(self, uid: str, title: str, due: datetime | None, completed: bool) -> str:
        collection = self._list(create=True)
        assert collection is not None
        calendar = Calendar()
        calendar.add("prodid", "-//Lora v2//Daily Driver//RO")
        calendar.add("version", "2.0")
        todo = Todo()
        todo.add("uid", uid)
        todo.add("summary", title)
        todo.add("dtstamp", datetime.now(timezone.utc))
        todo.add("status", "COMPLETED" if completed else "NEEDS-ACTION")
        if due:
            todo.add("dtstart", due)
            todo.add("due", due)
            if not completed:
                alarm = Alarm()
                alarm.add("action", "DISPLAY")
                alarm.add("description", title)
                alarm.add("trigger", timedelta(minutes=0))
                todo.add_component(alarm)
        if completed:
            todo.add("completed", datetime.now(timezone.utc))
        calendar.add_component(todo)
        remote = self._find_todo(collection, uid)
        if remote:
            remote.data = calendar.to_ical().decode()
            remote.save()
        else:
            remote = collection.add_todo(calendar.to_ical())
        return _snapshot(remote)[1]

    def get_revision(self, uid: str) -> str | None:
        collection = self._list()
        if collection is None:
            return None
        todo = self._find_todo(collection, uid)
        return _snapshot(todo)[1] if todo else None

    def delete(self, uid: str) -> None:
        collection = self._list()
        if collection is None:
            return
        todo = self._find_todo(collection, uid)
        if todo:
            todo.delete()

    def list_all(self) -> list[tuple[str, str, str, datetime | None, bool]]:
        collection = self._list()
        if collection is None:
            return []
        snapshots = []
        for todo in collection.todos(include_completed=True):
            uid, revision, due, completed = _snapshot(todo)
            component = Calendar.from_ical(todo.data).walk("VTODO")[0]
            snapshots.append((uid, revision, str(component.get("summary", "")), due, completed))
        return snapshots


async def push_pending(pool: asyncpg.Pool, settings: Settings, owner_id: int) -> int:
    """Push local changes; keep the outbox pending if Apple rejects the write."""
    if not settings.icloud_username or not settings.icloud_app_password:
        return 0
    remote = AppleRemote(settings)
    sent = 0
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """UPDATE notification_outbox SET status='leased',lease_until=now()+interval '2 minutes',attempts=attempts+1
            WHERE id IN (SELECT id FROM notification_outbox
              WHERE owner_id=$1 AND channel='apple' AND due_at<=now()
              AND (status='pending' OR (status='leased' AND lease_until<now()))
              ORDER BY due_at LIMIT 20 FOR UPDATE SKIP LOCKED)
            RETURNING id,payload,kind,attempts""",
            owner_id,
        )
    for row in rows:
        payload = json.loads(row["payload"])
        kind = payload["entity_type"]
        if kind not in ("task", "calendar_entry"):
            continue
        entity_id = uuid.UUID(payload["entity_id"])
        try:
            async with pool.acquire() as conn:
                link = await conn.fetchrow(
                    """SELECT apple_uid,apple_revision FROM apple_links
                    WHERE owner_id=$1 AND entity_type=$2 AND entity_id=$3""",
                    owner_id, kind, entity_id,
                )
                uid = link["apple_uid"] if link else f"lora-v2-{kind}-{entity_id}@lora"
                conflict = await conn.fetchval(
                    """SELECT 1 FROM apple_sync_conflicts WHERE owner_id=$1 AND entity_type=$2
                    AND entity_id=$3 AND status='pending'""",
                    owner_id, kind, entity_id,
                )
                if kind == "task":
                    entity = await conn.fetchrow(
                        "SELECT title,due_at,status,version FROM tasks WHERE id=$1 AND owner_id=$2",
                        entity_id, owner_id,
                    )
                    title = entity["title"] if entity else ""
                    due = entity["due_at"] if entity else None
                    completed = bool(entity and entity["status"] == "done")
                    deleted = not entity or entity["status"] == "cancelled"
                else:
                    entity = await conn.fetchrow(
                        "SELECT title,starts_at,status,kind,version FROM calendar_entries WHERE id=$1 AND owner_id=$2",
                        entity_id, owner_id,
                    )
                    title = entity["title"] if entity else ""
                    due = entity["starts_at"] if entity else None
                    completed = bool(entity and entity["status"] == "done")
                    deleted = not entity or entity["status"] == "cancelled" or entity["kind"] != "reminder"
            if conflict:
                raise RuntimeError("Apple sync conflict awaiting review")
            remote_revision = await asyncio.to_thread(remote.get_revision, uid)
            desired_revision = _digest(title, due, completed) if not deleted else None
            if ((link and remote_revision != link["apple_revision"])
                    or (not link and remote_revision and remote_revision != desired_revision)):
                async with pool.acquire() as conn:
                    await conn.execute(
                        """INSERT INTO apple_sync_conflicts(id,owner_id,entity_type,entity_id,apple_uid,local_version,apple_revision)
                        VALUES ($1,$2,$3,$4,$5,$6,$7) ON CONFLICT DO NOTHING""",
                        uuid.uuid4(), owner_id, kind, entity_id, uid,
                        entity["version"] if entity else 0, remote_revision,
                    )
                raise RuntimeError("Apple changed since last sync")
            if deleted:
                await asyncio.to_thread(remote.delete, uid)
                revision = None
            else:
                revision = await asyncio.to_thread(remote.upsert, uid, title, due, completed)
            async with pool.acquire() as conn:
                async with conn.transaction():
                    if entity and not deleted and revision:
                        await conn.execute(
                            """INSERT INTO apple_links(owner_id,entity_type,entity_id,apple_uid,apple_revision,last_synced_version,last_seen_at,missing_since)
                            VALUES ($1,$2,$3,$4,$5,$6,now(),NULL)
                            ON CONFLICT (owner_id,entity_type,entity_id) DO UPDATE SET
                            apple_revision=EXCLUDED.apple_revision,last_synced_version=EXCLUDED.last_synced_version,
                            last_seen_at=now(),missing_since=NULL""",
                            owner_id, kind, entity_id, uid, revision, entity["version"],
                        )
                    elif deleted:
                        await conn.execute(
                            """DELETE FROM apple_links WHERE owner_id=$1 AND entity_type=$2 AND entity_id=$3""",
                            owner_id, kind, entity_id,
                        )
                    await conn.execute(
                        "UPDATE notification_outbox SET status='sent',sent_at=now(),lease_until=NULL WHERE id=$1",
                        row["id"],
                    )
            sent += 1
        except Exception as exc:
            async with pool.acquire() as conn:
                await conn.execute(
                    """UPDATE notification_outbox SET status='pending',lease_until=NULL,
                    due_at=now()+interval '5 minutes',last_error=$2 WHERE id=$1""",
                    row["id"], type(exc).__name__,
                )
    return sent


async def pull_changes(pool: asyncpg.Pool, settings: Settings, owner_id: int) -> dict[str, int]:
    """Import Apple edits only when the local version still matches the last sync."""
    if not settings.icloud_username or not settings.icloud_app_password:
        return {"imported": 0, "updated": 0, "conflicts": 0}
    snapshots = await asyncio.to_thread(AppleRemote(settings).list_all)
    counts = {"imported": 0, "updated": 0, "conflicts": 0}
    seen_uids = {snapshot[0] for snapshot in snapshots}
    for uid, revision, title, due, completed in snapshots:
        async with pool.acquire() as conn:
            async with conn.transaction():
                link = await conn.fetchrow(
                    """SELECT entity_type,entity_id,apple_revision,last_synced_version FROM apple_links
                    WHERE owner_id=$1 AND apple_uid=$2 FOR UPDATE""",
                    owner_id, uid,
                )
                if link is None:
                    if uid.startswith("lora-v2-") and uid.endswith("@lora"):
                        linked_kind = "task" if uid.startswith("lora-v2-task-") else "calendar_entry"
                        try:
                            linked_id = uuid.UUID(uid.removeprefix(f"lora-v2-{linked_kind}-").removesuffix("@lora"))
                        except ValueError:
                            linked_id = None
                        if linked_id:
                            table_query = (
                                "SELECT version FROM tasks WHERE id=$1 AND owner_id=$2" if linked_kind == "task"
                                else "SELECT version FROM calendar_entries WHERE id=$1 AND owner_id=$2"
                            )
                            existing_version = await conn.fetchval(table_query, linked_id, owner_id)
                            if existing_version:
                                await conn.execute(
                                    """INSERT INTO apple_links(owner_id,entity_type,entity_id,apple_uid,apple_revision,last_synced_version,last_seen_at)
                                    VALUES ($1,$2,$3,$4,$5,$6,now())""",
                                    owner_id, linked_kind, linked_id, uid, revision, existing_version,
                                )
                                continue
                    entity_id = uuid.uuid4()
                    if due:
                        await conn.execute(
                            """INSERT INTO calendar_entries(id,owner_id,kind,title,starts_at,status)
                            VALUES ($1,$2,'reminder',$3,$4,$5)""",
                            entity_id, owner_id, title, due, "done" if completed else "active",
                        )
                        entity_type = "calendar_entry"
                        if not completed:
                            await conn.execute(
                                """INSERT INTO alert_occurrences(id,owner_id,entry_id,alert_at,purpose)
                                VALUES ($1,$2,$3,$4,'before_0m')""",
                                uuid.uuid4(), owner_id, entity_id, due,
                            )
                    else:
                        await conn.execute(
                            "INSERT INTO tasks(id,owner_id,title,status) VALUES ($1,$2,$3,$4)",
                            entity_id, owner_id, title, "done" if completed else "pending",
                        )
                        entity_type = "task"
                    await conn.execute(
                        """INSERT INTO apple_links(owner_id,entity_type,entity_id,apple_uid,apple_revision,last_synced_version,last_seen_at)
                        VALUES ($1,$2,$3,$4,$5,1,now())""",
                        owner_id, entity_type, entity_id, uid, revision,
                    )
                    counts["imported"] += 1
                    continue
                await conn.execute(
                    "UPDATE apple_links SET last_seen_at=now(),missing_since=NULL WHERE owner_id=$1 AND apple_uid=$2",
                    owner_id, uid,
                )
                if revision == link["apple_revision"]:
                    continue
                if link["entity_type"] == "task":
                    current = await conn.fetchrow(
                        "SELECT version,status FROM tasks WHERE id=$1 AND owner_id=$2 FOR UPDATE",
                        link["entity_id"], owner_id,
                    )
                else:
                    current = await conn.fetchrow(
                        "SELECT version,status FROM calendar_entries WHERE id=$1 AND owner_id=$2 FOR UPDATE",
                        link["entity_id"], owner_id,
                    )
                if not current or current["version"] != link["last_synced_version"]:
                    await conn.execute(
                        """INSERT INTO apple_sync_conflicts(id,owner_id,entity_type,entity_id,apple_uid,local_version,apple_revision)
                        VALUES ($1,$2,$3,$4,$5,$6,$7) ON CONFLICT DO NOTHING""",
                        uuid.uuid4(), owner_id, link["entity_type"], link["entity_id"], uid,
                        current["version"] if current else 0, revision,
                    )
                    counts["conflicts"] += 1
                    continue
                if link["entity_type"] == "calendar_entry" and not due:
                    await conn.execute(
                        """INSERT INTO apple_sync_conflicts(id,owner_id,entity_type,entity_id,apple_uid,local_version,apple_revision)
                        VALUES ($1,$2,$3,$4,$5,$6,$7) ON CONFLICT DO NOTHING""",
                        uuid.uuid4(), owner_id, link["entity_type"], link["entity_id"], uid,
                        current["version"], revision,
                    )
                    counts["conflicts"] += 1
                    continue
                if link["entity_type"] == "task":
                    await conn.execute(
                        """UPDATE tasks SET title=$3,due_at=$4,status=$5,version=version+1,updated_at=now()
                        WHERE id=$1 AND owner_id=$2""",
                        link["entity_id"], owner_id, title, due,
                        "done" if completed else "pending",
                    )
                elif due:
                    await conn.execute(
                        """UPDATE calendar_entries SET title=$3,starts_at=$4,status=$5,version=version+1,updated_at=now()
                        WHERE id=$1 AND owner_id=$2""",
                        link["entity_id"], owner_id, title, due,
                        "done" if completed else "active",
                    )
                    await conn.execute(
                        "UPDATE alert_occurrences SET status='cancelled' WHERE entry_id=$1 AND status='pending'",
                        link["entity_id"],
                    )
                    if not completed:
                        await conn.execute(
                            """INSERT INTO alert_occurrences(id,owner_id,entry_id,alert_at,purpose)
                            VALUES ($1,$2,$3,$4,'before_0m') ON CONFLICT DO NOTHING""",
                            uuid.uuid4(), owner_id, link["entity_id"], due,
                        )
                await conn.execute(
                    """UPDATE apple_links SET apple_revision=$3,last_synced_version=$4,last_seen_at=now()
                    WHERE owner_id=$1 AND apple_uid=$2""",
                    owner_id, uid, revision, current["version"] + 1,
                )
                counts["updated"] += 1
    # A vanished VTODO can be a remote deletion or a transient CalDAV listing
    # failure. Never delete local data silently: ask for review after two polls.
    async with pool.acquire() as conn:
        async with conn.transaction():
            links = await conn.fetch(
                """SELECT entity_type,entity_id,apple_uid,last_synced_version,missing_since
                FROM apple_links WHERE owner_id=$1 FOR UPDATE""",
                owner_id,
            )
            for link in links:
                if link["apple_uid"] in seen_uids:
                    continue
                if link["missing_since"] is None:
                    await conn.execute(
                        """UPDATE apple_links SET missing_since=now()
                        WHERE owner_id=$1 AND apple_uid=$2""",
                        owner_id, link["apple_uid"],
                    )
                    continue
                if link["missing_since"] > datetime.now(timezone.utc) - timedelta(minutes=5):
                    continue
                inserted = await conn.fetchval(
                    """INSERT INTO apple_sync_conflicts(id,owner_id,entity_type,entity_id,
                    apple_uid,local_version,apple_revision)
                    VALUES ($1,$2,$3,$4,$5,$6,NULL)
                    ON CONFLICT DO NOTHING RETURNING id""",
                    uuid.uuid4(), owner_id, link["entity_type"], link["entity_id"],
                    link["apple_uid"], link["last_synced_version"],
                )
                counts["conflicts"] += bool(inserted)
    return counts


async def resolve_conflict(
    pool: asyncpg.Pool,
    settings: Settings,
    owner_id: int,
    conflict_id: uuid.UUID,
    choice: Literal["keep_local", "use_apple"],
) -> str:
    """Apply an explicit user choice, checking both sides are still at the reviewed versions."""
    async with pool.acquire() as conn:
        conflict = await conn.fetchrow(
            """SELECT entity_type,entity_id,apple_uid,local_version,apple_revision,status
            FROM apple_sync_conflicts WHERE id=$1 AND owner_id=$2""",
            conflict_id, owner_id,
        )
    if not conflict or conflict["status"] != "pending":
        raise ValueError("Conflictul nu mai este disponibil")
    remote = AppleRemote(settings)
    snapshots = await asyncio.to_thread(remote.list_all)
    selected = next((item for item in snapshots if item[0] == conflict["apple_uid"]), None)
    current_revision = selected[1] if selected else None
    if current_revision != conflict["apple_revision"]:
        raise ValueError("Apple Reminders s-a schimbat din nou. Reîncarcă înainte de alegere")

    async with pool.acquire() as conn:
        async with conn.transaction():
            if conflict["entity_type"] == "task":
                entity = await conn.fetchrow(
                    "SELECT version,status FROM tasks WHERE id=$1 AND owner_id=$2 FOR UPDATE",
                    conflict["entity_id"], owner_id,
                )
            else:
                entity = await conn.fetchrow(
                    "SELECT version,status FROM calendar_entries WHERE id=$1 AND owner_id=$2 FOR UPDATE",
                    conflict["entity_id"], owner_id,
                )
            if not entity or entity["version"] != conflict["local_version"]:
                raise ValueError("Elementul local s-a schimbat. Reîncarcă înainte de alegere")
            if choice == "keep_local":
                await conn.execute(
                    """UPDATE apple_links SET apple_revision=$3,missing_since=NULL,last_seen_at=now()
                    WHERE owner_id=$1 AND apple_uid=$2""",
                    owner_id, conflict["apple_uid"], current_revision,
                )
                await conn.execute(
                    """INSERT INTO notification_outbox(id,owner_id,dedupe_key,channel,kind,payload)
                    VALUES ($1,$2,$3,'apple','upsert',$4::jsonb) ON CONFLICT DO NOTHING""",
                    uuid.uuid4(), owner_id, f"resolve:{conflict_id}:keep_local",
                    json.dumps({"entity_type": conflict["entity_type"],
                                "entity_id": str(conflict["entity_id"]), "operation": "upsert"}),
                )
                message = "Am păstrat varianta Lora. Voi actualiza Apple Reminders."
            else:
                if selected is None:
                    if conflict["entity_type"] == "task":
                        await conn.execute(
                            """UPDATE tasks SET status='cancelled',version=version+1,updated_at=now()
                            WHERE id=$1 AND owner_id=$2""",
                            conflict["entity_id"], owner_id,
                        )
                    else:
                        await conn.execute(
                            """UPDATE calendar_entries SET status='cancelled',version=version+1,updated_at=now()
                            WHERE id=$1 AND owner_id=$2""",
                            conflict["entity_id"], owner_id,
                        )
                        await conn.execute(
                            "UPDATE alert_occurrences SET status='cancelled' WHERE entry_id=$1 AND status='pending'",
                            conflict["entity_id"],
                        )
                    await conn.execute(
                        "DELETE FROM apple_links WHERE owner_id=$1 AND apple_uid=$2",
                        owner_id, conflict["apple_uid"],
                    )
                    message = "Am acceptat ștergerea din Apple Reminders."
                else:
                    _, revision, title, due, completed = selected
                    if conflict["entity_type"] == "task":
                        await conn.execute(
                            """UPDATE tasks SET title=$3,due_at=$4,status=$5,version=version+1,updated_at=now()
                            WHERE id=$1 AND owner_id=$2""",
                            conflict["entity_id"], owner_id, title, due,
                            "done" if completed else "pending",
                        )
                    else:
                        if due is None:
                            raise ValueError("Reminderul Apple nu are oră. Adaugă o oră în Apple sau păstrează varianta Lora")
                        await conn.execute(
                            """UPDATE calendar_entries SET title=$3,starts_at=$4,status=$5,
                            version=version+1,updated_at=now() WHERE id=$1 AND owner_id=$2""",
                            conflict["entity_id"], owner_id, title, due,
                            "done" if completed else "active",
                        )
                        await conn.execute(
                            "UPDATE alert_occurrences SET status='cancelled' WHERE entry_id=$1 AND status='pending'",
                            conflict["entity_id"],
                        )
                        if not completed:
                            await conn.execute(
                                """INSERT INTO alert_occurrences(id,owner_id,entry_id,alert_at,purpose)
                                VALUES ($1,$2,$3,$4,'before_0m') ON CONFLICT DO NOTHING""",
                                uuid.uuid4(), owner_id, conflict["entity_id"], due,
                            )
                    await conn.execute(
                        """UPDATE apple_links SET apple_revision=$3,last_synced_version=$4,
                        missing_since=NULL,last_seen_at=now() WHERE owner_id=$1 AND apple_uid=$2""",
                        owner_id, conflict["apple_uid"], revision, entity["version"] + 1,
                    )
                    message = "Am preluat varianta din Apple Reminders."
                await conn.execute(
                    """UPDATE notification_outbox SET status='sent',last_error='superseded_by_apple_choice'
                    WHERE owner_id=$1 AND channel='apple' AND status IN ('pending','leased')
                    AND payload->>'entity_id'=$2""",
                    owner_id, str(conflict["entity_id"]),
                )
            await conn.execute(
                "UPDATE apple_sync_conflicts SET status='resolved' WHERE id=$1 AND owner_id=$2",
                conflict_id, owner_id,
            )
    return message
