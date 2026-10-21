"""Moodle materials and forum updates move into Files and the Lora inbox."""

import os
import uuid
from pathlib import Path

import pytest

from lora_v2.config import Settings
from lora_v2.db import create_pool, migrate
from lora_v2.moodle_library import _discussion_posts, _is_relevant_post, ingest_course


def _forum(title: str, discussion: str, body: str, author: str = "POP Fănuța") -> dict[str, object]:
    url = f"https://econ.elearning.ubbcluj.ro/moodle/mod/forum/discuss.php?d={discussion}"
    return {"item_type": "forum", "title": title,
            "content": f"### {body}\n\n**Autor:** {author}\n\n**Sursă discuție:** [{url}]({url})"}


def test_forum_messages_are_separate_from_announcements() -> None:
    course = {"sections": [{"title": "General", "items": [
        _forum("Announcements Forum", "101", "Program nou"),
        _forum("Forum de discuții", "102", "Întrebare seminar"),
    ]}]}
    posts = _discussion_posts(course)
    assert [post["kind"] for post in posts] == ["announcement", "forum"]


def test_student_case_studies_do_not_enter_news() -> None:
    announcement = {"kind": "announcement", "body": "**Autor:** Student"}
    student = {"kind": "forum", "body": "### Studiu de caz\n\n**Autor:** Chiș Sara-Maria"}
    teacher = {"kind": "forum", "body": "### Seminar\n\n**Autor:** POP Fănuța"}
    assert _is_relevant_post(announcement, None)
    assert not _is_relevant_post(student, "Dabija / Sabo")
    assert _is_relevant_post(teacher, "Pop")
    assert not _is_relevant_post(teacher, None)


@pytest.mark.asyncio
async def test_moodle_import_baselines_old_posts_then_notifies_once_for_new_discussion(tmp_path: Path) -> None:
    url = os.getenv("LORA_V2_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Requires an isolated Lora v2 test database")
    settings = Settings(database_url=url, telegram_bot_token="test", telegram_user_id=123)
    owner = uuid.uuid4().int % 1000000000
    pool = await create_pool(settings)
    downloads = tmp_path / "downloads"
    source = downloads / "material.pdf"
    downloads.mkdir()
    source.write_bytes(b"safe course material")
    import hashlib
    attachment = {"downloaded_path": str(source), "name": "material.pdf",
                  "url": "https://econ.elearning.ubbcluj.ro/moodle/pluginfile.php/123/material.pdf",
                  "sha256": hashlib.sha256(source.read_bytes()).hexdigest()}
    course = {
        "course": "Analiză financiară_EG3_26-27",
        "source_url": "https://econ.elearning.ubbcluj.ro/moodle/course/view.php?id=123",
        "sections": [{"title": "C1", "items": [
            {"item_type": "file", "title": "Material 1", "attachments": [attachment]},
            _forum("Forum de discuții", "101", "Întrebare veche"),
        ]}],
    }
    student_post = _forum("Forum de discuții", "103", "Studiu de caz", "Chiș Sara-Maria")
    course["sections"][0]["items"].append(student_post)
    root = tmp_path / "icloud"
    try:
        await migrate(pool)
        await pool.execute(
            "INSERT INTO academic_subjects(id,owner_id,name,professor) VALUES ($1,$2,$3,$4)",
            uuid.uuid4(), owner, "Analiză financiară", "Pop",
        )
        first = await ingest_course(pool, owner, course, root=root, downloads_root=downloads)
        assert first["materials"] == 1 and first["notifications"] == 0
        assert (root / "Analiză financiară" / "Săptămâna 1" / "material.pdf").read_bytes() == source.read_bytes()
        assert await pool.fetchval("SELECT is_read FROM moodle_posts WHERE owner_id=$1", owner)
        assert await pool.fetchval("SELECT count(*) FROM moodle_posts WHERE owner_id=$1", owner) == 1
        course["sections"][0]["items"].append(_forum("Announcements Forum", "102", "Anunț nou"))
        second = await ingest_course(pool, owner, course, root=root, downloads_root=downloads)
        assert second["notifications"] == 1
        assert (await ingest_course(pool, owner, course, root=root, downloads_root=downloads))["notifications"] == 0
        assert await pool.fetchval("SELECT count(*) FROM moodle_materials WHERE owner_id=$1", owner) == 1
        assert await pool.fetchval("SELECT count(*) FROM notification_outbox WHERE owner_id=$1 AND kind='moodle_post'", owner) == 1
        assert await pool.fetchval("SELECT count(*) FROM moodle_posts WHERE owner_id=$1 AND is_read=false", owner) == 1
        source.write_bytes(b"revised course material")
        attachment["sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
        await ingest_course(pool, owner, course, root=root, downloads_root=downloads)
        retained = root / "Analiză financiară" / "Săptămâna 1" / "material.pdf"
        assert retained.read_bytes() == b"safe course material"
        assert (retained.parent / f"material-{attachment['sha256'][:10]}.pdf").read_bytes() == source.read_bytes()
        assert await pool.fetchval("SELECT count(*) FROM moodle_materials WHERE owner_id=$1", owner) == 2
        student_url = "https://econ.elearning.ubbcluj.ro/moodle/mod/forum/discuss.php?d=103"
        await pool.execute(
            """INSERT INTO moodle_posts(id,owner_id,course_url,course_title,forum_title,kind,
            discussion_url,title,body,content_hash) VALUES ($1,$2,$3,$4,$5,'forum',$6,$7,$8,$9)""",
            uuid.uuid4(), owner, course["source_url"], course["course"], "Forum de discuții",
            student_url, "Studiu de caz", "Predare veche", "old-hash",
        )
        await ingest_course(pool, owner, course, root=root, downloads_root=downloads)
        assert await pool.fetchval(
            "SELECT archived_at IS NOT NULL FROM moodle_posts WHERE owner_id=$1 AND discussion_url=$2",
            owner, student_url,
        )
    finally:
        await pool.close()
