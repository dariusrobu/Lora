"""V2 projections into existing vault files; manual bodies and folders are preserved.

Only timetable scalar fields are imported (the existing Obsidian contract).
Absent notes never delete data. Simultaneous changes are retained as conflicts.
"""

import json
import hashlib
import os
import re
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Any

import asyncpg
import yaml

from lora_v2.academics import Schedule, write_academic

SCHEDULE_FIELDS = ('day_of_week', 'start_time', 'end_time', 'room', 'class_type', 'week_type')
# Queries are static; filenames and document contents never become SQL.
EXPORTS = {
    'schedule': ("06 Calendar/_Schedule", "SELECT id,legacy_id,version,title AS subject_name,day_of_week,start_time,end_time,room,class_type,week_type,is_active FROM academic_schedule_rules WHERE owner_id=$1"),
    'university_subject': ("05 University/_Data/Subjects", "SELECT id,legacy_id,version,name,professor,credits,is_active FROM academic_subjects WHERE owner_id=$1"),
    'task': ("02 Tasks/_Active", "SELECT id,legacy_id,version,title,notes AS description,status,due_at FROM tasks WHERE owner_id=$1"),
    'project': ("03 Projects", "SELECT id,legacy_id,version,name,status FROM projects WHERE owner_id=$1"),
    'event': ("06 Calendar/_Events", "SELECT id,legacy_id,version,title,notes AS description,kind AS event_type,starts_at,ends_at,status FROM calendar_entries WHERE owner_id=$1 AND kind!='academic'"),
    'grade': ("05 University/_Data/Grades", "SELECT id,legacy_id,version,value AS grade,label AS grade_type,recorded_at,deleted_at FROM academic_grades WHERE owner_id=$1"),
    'attendance': ("05 University/_Data/Attendance", "SELECT id,legacy_id,version,class_date,attended,notes,deleted_at FROM academic_attendance WHERE owner_id=$1"),
    'exam': ("05 University/_Data/Exams", "SELECT id,legacy_id,version,title AS subject_name,starts_at AS exam_date,exam_type,room,notes,deleted_at FROM academic_exams WHERE owner_id=$1"),
}


def read_document(text: str) -> dict[str, Any]:
    match = re.match(r'\A---\r?\n(.*?)\r?\n---(?:\r?\n|$)', text, re.S)
    if not match:
        return {}
    data = yaml.safe_load(match.group(1))
    return data if isinstance(data, dict) else {}


def scalar(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, bool, float)):
        return value
    if hasattr(value, 'isoformat'):
        return value.isoformat()
    return str(value)


def patch_document(text: str, fields: dict[str, Any]) -> str:
    """Patch scalar frontmatter only; preserve unknown keys and body byte-for-byte."""
    match = re.match(r'\A---\r?\n(.*?)\r?\n---(?=\r?\n|$)', text, re.S)
    if text and not match:
        raise ValueError('Existing note has no frontmatter; refusing to replace it')
    header = match.group(1) if match else ''
    for key, value in fields.items():
        line = key + ': ' + json.dumps(scalar(value), ensure_ascii=False)
        pattern = r'^' + re.escape(key) + r':[^\r\n]*$'
        if re.search(pattern, header, re.M):
            header = re.sub(pattern, lambda _: line, header, flags=re.M)
        else:
            header += ('\n' if header else '') + line
    body = text[match.end():] if match else '\n\n'
    return '---\n' + header + '\n---' + body


def schedule_fields(data: dict[str, Any]) -> dict[str, Any]:
    result = {key: scalar(data.get(key)) for key in SCHEDULE_FIELDS}
    for key in ('room', 'class_type'):
        result[key] = result[key] or None
    for key in ('start_time', 'end_time'):
        if result[key] and len(str(result[key])) == 5:
            result[key] += ':00'
    if result['day_of_week'] is not None:
        result['day_of_week'] = int(result['day_of_week'])
    return result


def safe_write(path: Path, text: str, expected: str | None) -> None:
    # Detect edits made after the read. Atomic replace avoids partial iCloud files.
    current = path.read_text(encoding='utf-8') if path.exists() else None
    if current != expected:
        raise ValueError('Obsidian note changed during synchronization')
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name('.' + path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        temporary.write_text(text, encoding='utf-8')
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


async def sync_vault(pool: asyncpg.Pool, owner_id: int, vault: Path, dry_run: bool = False) -> dict[str, int]:
    vault = vault.expanduser().resolve()
    if not vault.is_dir():
        raise ValueError('Configured Obsidian vault is missing')
    index: dict[tuple[str, str], list[Path]] = {}
    for path in vault.rglob('*.md'):
        if (any(part.startswith('.') for part in path.relative_to(vault).parts)
                or path.relative_to(vault).parts[0] == '99 Archive' or path.is_symlink()):
            continue
        try:
            meta = read_document(path.read_text(encoding='utf-8'))
        except (ValueError, yaml.YAMLError):
            continue
        kind = str(meta.get('type', ''))
        for key in ('lora_id', 'lora_v2_id'):
            if meta.get(key) is not None:
                index.setdefault((kind, str(meta[key])), []).append(path)
    stats = {'exported': 0, 'imported': 0, 'unchanged': 0, 'conflicts': 0}
    for kind, (folder, query) in EXPORTS.items():
        rows = await pool.fetch(query, owner_id)
        for record in rows:
            row = dict(record)
            entity_id, version = row.pop('id'), row.pop('version')
            legacy_id = row.pop('legacy_id')
            state = await pool.fetchrow(
                'SELECT * FROM obsidian_documents WHERE owner_id=$1 AND kind=$2 AND entity_id=$3', owner_id, kind, entity_id,
            )
            matches = set(index.get((kind, str(entity_id)), []) + index.get((kind, str(legacy_id)), []))
            if kind == 'university_subject' and len(matches) > 1:
                canonical = {p for p in matches if not p.is_relative_to(vault / '05 University' / 'Subjects')}
                if len(canonical) == 1:
                    matches = canonical
            if not matches and not state and (row.get('is_active') is False or row.get('deleted_at') or row.get('status') in ('done', 'cancelled')):
                stats['unchanged'] += 1
                continue
            if len(matches) > 1:
                stats['conflicts'] += 1
                continue
            if state:
                path = (vault / state['relative_path']).resolve()
                if not path.is_relative_to(vault) or not path.exists():
                    # Missing files may be moved/offline; never recreate or delete blindly.
                    stats['conflicts'] += 1
                    continue
            else:
                path = next(iter(matches), vault / folder / ('v2-' + str(entity_id) + '.md'))
            if not path.resolve().is_relative_to(vault):
                stats['conflicts'] += 1
                continue
            existing = path.read_text(encoding='utf-8') if path.exists() else None
            meta = read_document(existing or '')
            desired = {key: scalar(value.astimezone(ZoneInfo(os.getenv('TIMEZONE', 'Europe/Bucharest'))) if isinstance(value, datetime) else value) for key, value in row.items()}
            conflict = None
            if kind == 'schedule' and existing:
                remote = schedule_fields(meta)
                local = schedule_fields(desired)
                baseline = json.loads(state['file_fields']) if state else None
                changed_file = baseline is not None and remote != baseline
                changed_db = state is not None and state['entity_version'] != version
                if remote != local:
                    if not state or state['conflict'] or (changed_file and changed_db):
                        conflict = 'timetable_changed_in_both_sources' if state else 'initial_timetable_difference'
                    elif changed_file:
                        if not dry_run:
                            full = dict(await pool.fetchrow('SELECT * FROM academic_schedule_rules WHERE id=$1 AND owner_id=$2', entity_id, owner_id))
                            payload = {k: full[k] for k in Schedule.model_fields}
                            payload.update(remote)
                            result = await write_academic(pool, owner_id, 'schedule', payload, entity_id, version)
                            version = result['version']
                        desired.update(remote)
                        stats['imported'] += 1
            if conflict:
                stats['conflicts'] += 1
                if not dry_run:
                    await pool.execute(
                        """INSERT INTO obsidian_documents(owner_id,kind,entity_id,relative_path,file_fields,entity_version,conflict)
                        VALUES ($1,$2,$3,$4,$5::jsonb,$6,$7) ON CONFLICT(owner_id,kind,entity_id)
                        DO UPDATE SET conflict=EXCLUDED.conflict,entity_version=EXCLUDED.entity_version""",
                        owner_id, kind, entity_id, str(path.relative_to(vault)), json.dumps(schedule_fields(meta)), version, conflict,
                    )
                continue
            fields = {'type': kind, 'lora_id': legacy_id if legacy_id is not None else str(entity_id), 'lora_v2_id': str(entity_id), **desired}
            # Old Dataview consumers still use these names.
            if kind == 'task':
                fields['due_date'] = str(fields['due_at'])[:10] if fields.get('due_at') else None
            if kind == 'event':
                fields['event_date'] = str(fields['starts_at'])[:10]
                fields['event_time'] = str(fields['starts_at'])[11:19]
            updated = patch_document(existing or '', fields)
            if updated != existing:
                if not dry_run:
                    safe_write(path, updated, existing)
                stats['exported'] += 1
            else:
                stats['unchanged'] += 1
            if not dry_run:
                await pool.execute(
                    """INSERT INTO obsidian_documents(owner_id,kind,entity_id,relative_path,file_fields,entity_version)
                    VALUES ($1,$2,$3,$4,$5::jsonb,$6) ON CONFLICT(owner_id,kind,entity_id)
                    DO UPDATE SET relative_path=EXCLUDED.relative_path,file_fields=EXCLUDED.file_fields,
                    entity_version=EXCLUDED.entity_version,conflict=NULL,last_synced_at=now()""",
                    owner_id, kind, entity_id, str(path.relative_to(vault)),
                    json.dumps(schedule_fields(desired) if kind == 'schedule' else desired), version,
                )
    return stats


async def sync_configured_vault(pool: asyncpg.Pool, owner_id: int) -> None:
    path = os.getenv('OBSIDIAN_VAULT_PATH')
    if not path or os.getenv('OBSIDIAN_SYNC_ENABLED', 'true').lower() != 'true':
        return
    stats = await sync_vault(pool, owner_id, Path(path))
    await pool.execute(
        """INSERT INTO integration_status(name,status,detail) VALUES ('obsidian',$1,$2::jsonb)
        ON CONFLICT(name) DO UPDATE SET status=EXCLUDED.status,detail=EXCLUDED.detail,checked_at=now()""",
        'conflict' if stats['conflicts'] else 'ok', json.dumps(stats),
    )


async def list_schedule_conflicts(pool: asyncpg.Pool, owner_id: int, vault: Path) -> list[dict[str, Any]]:
    """Show only actionable timetable conflicts to the owner."""
    vault = vault.expanduser().resolve()
    rows = await pool.fetch(
        """SELECT d.entity_id,d.relative_path,d.conflict,r.title,r.version,
        r.day_of_week,r.start_time,r.end_time,r.room,r.class_type,r.week_type
        FROM obsidian_documents d JOIN academic_schedule_rules r ON r.id=d.entity_id
        WHERE d.owner_id=$1 AND d.kind='schedule' AND d.conflict IS NOT NULL
        AND r.owner_id=$1 ORDER BY d.relative_path""", owner_id,
    )
    result = []
    for row in rows:
        path = vault / row['relative_path']
        if path.is_symlink() or not path.resolve().is_relative_to(vault) or not path.is_file():
            continue
        content = path.read_text(encoding='utf-8')
        result.append({**dict(row), 'file_fields': schedule_fields(read_document(content)),
                       'file_revision': hashlib.sha256(content.encode()).hexdigest()})
    return result


async def resolve_schedule_conflict(
    pool: asyncpg.Pool, owner_id: int, vault: Path, entity_id: uuid.UUID,
    choice: str, expected_version: int, file_revision: str,
) -> None:
    """Apply an explicit choice if both copies still match the reviewed versions."""
    if choice not in {'keep_lora', 'use_obsidian'}:
        raise ValueError('Unknown Obsidian conflict choice')
    vault = vault.expanduser().resolve()
    async with pool.acquire() as conn:
        async with conn.transaction():
            state = await conn.fetchrow(
                """SELECT relative_path,file_fields,entity_version,conflict
                FROM obsidian_documents WHERE owner_id=$1 AND kind='schedule' AND entity_id=$2
                FOR UPDATE""", owner_id, entity_id,
            )
            if not state or not state['conflict'] or state['entity_version'] != expected_version:
                raise ValueError('Conflictul s-a schimbat. Reîncarcă înainte de alegere.')
            path = vault / state['relative_path']
            if path.is_symlink() or not path.resolve().is_relative_to(vault) or not path.is_file():
                raise ValueError('Nota Obsidian nu mai este disponibilă în locul așteptat.')
            existing = path.read_text(encoding='utf-8')
            if hashlib.sha256(existing.encode()).hexdigest() != file_revision:
                raise ValueError('Nota Obsidian a fost modificată. Reîncarcă înainte de alegere.')
            meta = read_document(existing)
            remote = schedule_fields(meta)
            full_row = await conn.fetchrow(
                'SELECT * FROM academic_schedule_rules WHERE id=$1 AND owner_id=$2',
                entity_id, owner_id,
            )
            if not full_row or full_row['version'] != expected_version:
                raise ValueError('Orarul Lora a fost modificat. Reîncarcă înainte de alegere.')
            if (str(meta.get('lora_v2_id')) != str(entity_id)
                    and (full_row['legacy_id'] is None
                         or str(meta.get('lora_id')) != str(full_row['legacy_id']))):
                raise ValueError('Nota Obsidian nu mai corespunde orarului selectat.')
            if choice == 'use_obsidian':
                payload = {key: full_row[key] for key in Schedule.model_fields}
                payload.update(remote)
                result = await write_academic(pool, owner_id, 'schedule', payload, entity_id, expected_version)
                version = result['version']
                fields = remote
            else:
                fields = schedule_fields(dict(full_row))
                safe_write(path, patch_document(existing, fields), existing)
                version = expected_version
            await conn.execute(
                """UPDATE obsidian_documents SET file_fields=$3::jsonb,entity_version=$4,
                conflict=NULL,last_synced_at=now()
                WHERE owner_id=$1 AND kind='schedule' AND entity_id=$2 AND conflict IS NOT NULL""",
                owner_id, entity_id, json.dumps(fields), version,
            )
