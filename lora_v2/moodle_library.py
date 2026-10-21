"""Read-only Moodle projection into iCloud Drive and Lora's university inbox."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import unicodedata
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import asyncpg


DEFAULT_ICLOUD_ROOT = Path.home() / "Library/Mobile Documents/com~apple~CloudDocs/Lora/Facultate"


def icloud_root() -> Path:
    return Path(os.getenv("LORA_MOODLE_ICLOUD_ROOT", str(DEFAULT_ICLOUD_ROOT))).expanduser()


def _safe_name(value: str, fallback: str) -> str:
    cleaned = re.sub(r"[/:*?\"<>|\\\x00-\x1f]", "-", value).strip(" .")
    return cleaned[:120] or fallback


def _subject_name(course: str) -> str:
    value = re.sub(r"_(?:SPE3\+FB3\+)?EG3_26-27$", "", course).strip()
    return _safe_name(value, "Materie")


def _section_name(title: str) -> str:
    match = re.search(r"(?:c|s|week|săptămâna|saptamana)\s*[- ]*([0-9]+)", title.casefold())
    return f"Săptămâna {int(match.group(1))}" if match else "Materiale generale"


def _digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def _copy_attachment(attachment: dict[str, Any], section: str, folder: str,
                     root: Path, downloads_root: Path) -> tuple[str, str, tuple[str, str] | None] | None:
    source = Path(str(attachment.get("downloaded_path") or ""))
    if not source.is_file() or source.is_symlink() or not source.resolve().is_relative_to(downloads_root.resolve()):
        return None
    expected = str(attachment.get("sha256") or "")
    digest = _digest(source)
    if expected and expected != digest:
        raise ValueError("Moodle attachment checksum changed before import")
    name = _safe_name(str(attachment.get("name") or source.name), "Material")
    target = root / folder / _section_name(section) / name
    if not target.resolve().is_relative_to(root.resolve()) or target.is_symlink():
        raise ValueError("Unsafe iCloud material path")
    target.parent.mkdir(parents=True, exist_ok=True)
    retained: tuple[str, str] | None = None
    if target.exists() and _digest(target) != digest:
        retained = (target.relative_to(root).as_posix(), _digest(target))
        target = target.with_name(f"{target.stem}-{digest[:10]}{target.suffix}")
    if target.is_symlink() or not target.resolve().is_relative_to(root.resolve()):
        raise ValueError("Unsafe iCloud material destination")
    if not target.exists():
        temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.part")
        try:
            shutil.copy2(source, temporary)
            if _digest(temporary) != digest:
                raise ValueError("Copied iCloud material checksum mismatch")
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)
    return target.relative_to(root).as_posix(), digest, retained


def _is_announcement(forum_title: str) -> bool:
    title = forum_title.casefold()
    return any(word in title for word in ("anunț", "anunt", "announcement", "news"))


def _words(value: str) -> list[str]:
    ascii_text = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().casefold()
    return re.findall(r"[a-z0-9]+", ascii_text)


def _author_name(body: str) -> str | None:
    match = re.search(r"^\*\*Autor:\*\*\s*(.+)$", body, flags=re.MULTILINE)
    return match.group(1).strip() if match else None


def _author_key(author_name: str) -> str:
    return " ".join(_words(author_name))


def _is_relevant_post(post: dict[str, str], professor: str | None,
                      trusted_authors: set[str] | None = None) -> bool:
    """Show designated announcements or forum discussions started by a known teacher."""
    if post["kind"] == "announcement":
        return True
    author = _author_name(post["body"])
    if not author:
        return False
    if _author_key(author) in (trusted_authors or set()):
        return True
    if not professor:
        return False
    author_words = set(_words(author))
    professor_words = set(_words(professor)) - {
        "prof", "profesor", "curs", "seminar", "conf", "univ", "doctor", "lector", "lect",
        "asist", "asistent", "disciplina", "responsabil", "cadru", "didactic",
    }
    return any(len(word) >= 3 and word in author_words for word in professor_words)


def _discussion_posts(course: dict[str, Any]) -> list[dict[str, str]]:
    posts: list[dict[str, str]] = []
    for section in course.get("sections", []):
        for forum in section.get("items", []):
            if forum.get("item_type") != "forum":
                continue
            kind = "announcement" if _is_announcement(str(forum.get("title") or "")) else "forum"
            content = str(forum.get("content") or "")
            for block in re.split(r"(?=^### )", content, flags=re.MULTILINE):
                block = block.strip()
                if not block.startswith("### "):
                    continue
                match = re.search(r"https://econ\.elearning\.ubbcluj\.ro/moodle/mod/forum/discuss\.php\?d=\d+", block)
                if not match:
                    continue
                source = match.group(0)
                parsed = urlparse(source)
                if parsed.hostname != "econ.elearning.ubbcluj.ro":
                    continue
                title = block.splitlines()[0].removeprefix("### ").strip()
                posts.append({"discussion_url": source, "title": title[:300], "body": block[:50000],
                              "forum_title": str(forum.get("title") or "Forum"), "kind": kind})
    return list({post["discussion_url"]: post for post in posts}.values())


async def ingest_course(pool: asyncpg.Pool, owner_id: int, course: dict[str, Any],
                        *, root: Path | None = None, downloads_root: Path | None = None) -> dict[str, Any]:
    """Copy verified files, then transactionally upsert posts and queue only later changes."""
    destination = (root or icloud_root()).expanduser()
    source_root = (downloads_root or Path(os.getenv("MOODLE_BRIDGE_OUTPUT_DIR", "scratch/moodle"))).resolve()
    course_url = str(course.get("source_url") or "")
    if not re.fullmatch(r"https://econ\.elearning\.ubbcluj\.ro/moodle/course/view\.php\?id=\d+", course_url):
        raise ValueError("Invalid Moodle course URL")
    title = str(course.get("course") or "Materie")
    folder = _subject_name(title)
    materials: list[tuple[str, str, str, str, str, str]] = []
    for section in course.get("sections", []):
        section_title = str(section.get("title") or "General")
        for item in section.get("items", []):
            for attachment in item.get("attachments", []):
                copied = _copy_attachment(attachment, section_title, folder, destination, source_root)
                if copied:
                    relative, digest, retained = copied
                    source_url = str(attachment.get("url") or item.get("source_url") or "")
                    materials.append((source_url, str(item.get("title") or "Material"),
                                      section_title, Path(relative).name, relative, digest))
                    if retained:
                        old_relative, old_digest = retained
                        materials.append(("retained-local:" + old_relative, Path(old_relative).name,
                                          "Material păstrat", Path(old_relative).name,
                                          old_relative, old_digest))
    posts = _discussion_posts(course)
    notifications = 0
    async with pool.acquire() as conn:
        async with conn.transaction():
            subject_rows = await conn.fetch(
                "SELECT name,professor FROM academic_subjects WHERE owner_id=$1 AND is_active=true",
                owner_id,
            )
            course_words = _words(title)
            subject = next((row for row in subject_rows
                            if course_words[:len(_words(row["name"]))] == _words(row["name"])), None)
            listed_professor = subject["professor"] if subject else None
            course_staff = course.get("teaching_staff") or []
            if not isinstance(course_staff, list):
                course_staff = []
            professor = " / ".join(
                part for part in [listed_professor, *course_staff] if isinstance(part, str) and part
            )
            trusted_authors = {
                row["author_key"] for row in await conn.fetch(
                    "SELECT author_key FROM moodle_trusted_authors WHERE owner_id=$1 AND course_url=$2",
                    owner_id, course_url,
                )
            }
            previous_course = await conn.fetchval(
                "SELECT 1 FROM moodle_course_sync WHERE owner_id=$1 AND course_url=$2 FOR UPDATE",
                owner_id, course_url,
            )
            for source_url, material_title, section_title, filename, relative, digest in materials:
                await conn.execute(
                    """INSERT INTO moodle_materials(id,owner_id,course_url,source_url,title,
                    section_title,filename,relative_path,sha256) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
                    ON CONFLICT (owner_id,course_url,source_url) DO UPDATE SET
                    title=EXCLUDED.title,section_title=EXCLUDED.section_title,
                    filename=EXCLUDED.filename,relative_path=EXCLUDED.relative_path,
                    sha256=EXCLUDED.sha256,last_seen_at=now()""",
                    uuid.uuid4(), owner_id, course_url, source_url, material_title,
                    section_title, filename, relative, digest,
                )
            for post in posts:
                source = post["discussion_url"]
                if not _is_relevant_post(post, professor, trusted_authors):
                    proposed_id = uuid.uuid5(uuid.NAMESPACE_URL, f"{owner_id}:{source}")
                    fingerprint = hashlib.sha256(post["body"].encode()).hexdigest()
                    excluded_id = await conn.fetchval(
                        """INSERT INTO moodle_posts(id,owner_id,course_url,course_title,forum_title,
                        kind,discussion_url,title,body,content_hash,is_read,archived_at,filtered_out)
                        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,true,now(),true)
                        ON CONFLICT (owner_id,discussion_url) DO UPDATE SET
                        course_title=EXCLUDED.course_title,forum_title=EXCLUDED.forum_title,
                        title=EXCLUDED.title,body=EXCLUDED.body,content_hash=EXCLUDED.content_hash,
                        archived_at=COALESCE(moodle_posts.archived_at,now()),filtered_out=true RETURNING id""",
                        proposed_id, owner_id, course_url, title, post["forum_title"],
                        post["kind"], source, post["title"], post["body"], fingerprint,
                    )
                    await conn.execute(
                        """UPDATE notification_outbox SET status='sent',last_error='filtered_student_post',
                        lease_until=NULL WHERE owner_id=$1 AND kind='moodle_post'
                        AND status IN ('pending','leased') AND dedupe_key LIKE $2""",
                        owner_id, f"moodle:{excluded_id}:%",
                    )
                    continue
                fingerprint = hashlib.sha256(post["body"].encode()).hexdigest()
                existing = await conn.fetchrow(
                    "SELECT id,content_hash,archived_at,filtered_out FROM moodle_posts WHERE owner_id=$1 AND discussion_url=$2 FOR UPDATE",
                    owner_id, source,
                )
                if existing and existing["content_hash"] == fingerprint:
                    if existing["filtered_out"]:
                        await conn.execute(
                            """UPDATE moodle_posts SET archived_at=NULL,is_read=true,filtered_out=false
                            WHERE id=$1 AND owner_id=$2""",
                            existing["id"], owner_id,
                        )
                    continue
                post_id = existing["id"] if existing else uuid.uuid5(uuid.NAMESPACE_URL, f"{owner_id}:{source}")
                if existing:
                    await conn.execute(
                        """UPDATE moodle_posts SET course_title=$3,forum_title=$4,kind=$5,title=$6,
                        body=$7,content_hash=$8,is_read=false,archived_at=NULL,
                        filtered_out=false,updated_at=now()
                        WHERE id=$1 AND owner_id=$2""",
                        post_id, owner_id, title, post["forum_title"], post["kind"],
                        post["title"], post["body"], fingerprint,
                    )
                else:
                    await conn.execute(
                        """INSERT INTO moodle_posts(id,owner_id,course_url,course_title,forum_title,
                        kind,discussion_url,title,body,content_hash,is_read)
                        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11) ON CONFLICT DO NOTHING""",
                        post_id, owner_id, course_url, title, post["forum_title"], post["kind"],
                        source, post["title"], post["body"], fingerprint, not bool(previous_course),
                    )
                if previous_course:
                    label = "anunț" if post["kind"] == "announcement" else "mesaj pe forum"
                    message = f"📚 {title}: {label} nou — {post['title']}\nDeschide Lora → Facultate → Noutăți Moodle."
                    inserted = await conn.fetchval(
                        """INSERT INTO notification_outbox(id,owner_id,dedupe_key,channel,kind,payload)
                        VALUES ($1,$2,$3,'telegram','moodle_post',$4::jsonb)
                        ON CONFLICT DO NOTHING RETURNING id""",
                        uuid.uuid4(), owner_id, f"moodle:{post_id}:{fingerprint}",
                        json.dumps({"text": message}, ensure_ascii=False),
                    )
                    notifications += bool(inserted)
            material_count = await conn.fetchval(
                "SELECT count(*) FROM moodle_materials WHERE owner_id=$1 AND course_url=$2",
                owner_id, course_url,
            )
            await conn.execute(
                """INSERT INTO moodle_course_sync(owner_id,course_url,course_title,folder_name,material_count)
                VALUES ($1,$2,$3,$4,$5) ON CONFLICT (owner_id,course_url) DO UPDATE SET
                course_title=EXCLUDED.course_title,folder_name=EXCLUDED.folder_name,
                material_count=EXCLUDED.material_count,last_synced_at=now()""",
                owner_id, course_url, title, folder, material_count,
            )
    return {"course": title, "folder": folder, "materials": len(materials),
            "posts": len(posts), "notifications": notifications}
