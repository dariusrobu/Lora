"""Moodle materials and forum updates move into Files and the Lora inbox."""

import hashlib
import hmac
import json
import os
import time
import uuid
from pathlib import Path
from urllib.parse import urlencode

import httpx
import pytest

from lora_v2.api import create_app
from lora_v2.config import Settings
from lora_v2.db import create_pool, migrate
from lora_v2.moodle_library import _author_key, _discussion_posts, _is_relevant_post, ingest_course


def _forum(title: str, discussion: str, body: str, author: str = "POP Fănuța") -> dict[str, object]:
    url = f"https://econ.elearning.ubbcluj.ro/moodle/mod/forum/discuss.php?d={discussion}"
    return {"item_type": "forum", "title": title,
            "content": f"### {body}\n\n**Autor:** {author}\n\n**Sursă discuție:** [{url}]({url})"}


def _auth(token: str, owner: int) -> str:
    values = {"auth_date": str(int(time.time())),
              "user": json.dumps({"id": owner}, separators=(",", ":"))}
    check = "\n".join(f"{key}={value}" for key, value in sorted(values.items()))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    values["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(values)


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
    assert _is_relevant_post(teacher, "Conf. univ. dr. Fănuța POP")
    assert not _is_relevant_post(teacher, None)
    assert _is_relevant_post(student, None, {_author_key("Chiș Sara-Maria")})


@pytest.mark.asyncio
async def test_moodle_import_baselines_old_posts_then_notifies_once_for_new_discussion(tmp_path: Path) -> None:
    url = os.getenv("LORA_V2_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Requires an isolated Lora v2 test database")
    owner = uuid.uuid4().int % 1000000000
    settings = Settings(database_url=url, telegram_bot_token="test", telegram_user_id=owner)
    pool = await create_pool(settings)
    downloads = tmp_path / "downloads"
    source = downloads / "material.pdf"
    downloads.mkdir()
    source.write_bytes(b"safe course material")
    attachment = {"downloaded_path": str(source), "name": "material.pdf",
                  "url": "https://econ.elearning.ubbcluj.ro/moodle/pluginfile.php/123/material.pdf",
                  "sha256": hashlib.sha256(source.read_bytes()).hexdigest()}
    course = {
        "course": "Analiză financiară_EG3_26-27",
        "teaching_staff": ["Conf. univ. dr. Fănuța POP"],
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
        first = await ingest_course(pool, owner, course, root=root, downloads_root=downloads)
        assert first["materials"] == 1 and first["notifications"] == 0
        assert (root / "Analiză financiară" / "Săptămâna 1" / "material.pdf").read_bytes() == source.read_bytes()
        assert await pool.fetchval("SELECT is_read FROM moodle_posts WHERE owner_id=$1 AND archived_at IS NULL", owner)
        assert await pool.fetchval("SELECT count(*) FROM moodle_posts WHERE owner_id=$1", owner) == 2
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
        await ingest_course(pool, owner, course, root=root, downloads_root=downloads)
        assert await pool.fetchval(
            "SELECT archived_at IS NOT NULL FROM moodle_posts WHERE owner_id=$1 AND discussion_url=$2",
            owner, student_url,
        )
        app = create_app(settings)
        async with app.router.lifespan_context(app):
            headers = {"X-Telegram-Init-Data": _auth(settings.telegram_bot_token, owner)}
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                authors = await client.get("/api/v2/moodle/authors", headers=headers)
                assert authors.status_code == 200
                student = next(row for row in authors.json() if row["author_name"] == "Chiș Sara-Maria")
                assert not student["visible"] and not student["followed"]
                followed = await client.put("/api/v2/moodle/authors", headers=headers,
                                            json={"course_url": course["source_url"],
                                                  "author_name": "Chiș Sara-Maria", "follow": True})
                assert followed.status_code == 200
        following = await ingest_course(pool, owner, course, root=root, downloads_root=downloads)
        assert following["notifications"] == 0
        assert await pool.fetchval(
            "SELECT archived_at IS NULL FROM moodle_posts WHERE owner_id=$1 AND discussion_url=$2",
            owner, student_url,
        )
        course["sections"][0]["items"].append(
            _forum("Forum de discuții", "104", "Program pentru săptămâna viitoare", "Chiș Sara-Maria")
        )
        new_post = await ingest_course(pool, owner, course, root=root, downloads_root=downloads)
        assert new_post["notifications"] == 1
        assert await pool.fetchval(
            "SELECT count(*) FROM notification_outbox WHERE owner_id=$1 AND kind='moodle_post'",
            owner,
        ) == 2
    finally:
        await pool.close()
