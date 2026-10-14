from pathlib import Path
from typing import Any

import pytest

from integrations.moodle_files import (
    allowed_material_url, attachment_filename, download_material,
)
from integrations.moodle_readonly import parse_course_html, parse_section_links
from scripts.moodle_bridge import _save_to_vault, _write_generated

BASE = "https://econ.elearning.ubbcluj.ro/moodle/"
RESOURCE = BASE + "mod/resource/view.php?id=1"
PDF = BASE + "pluginfile.php/2/mod_resource/content/1/lecture.pdf"


class Response:
    def __init__(self, body: bytes, headers: dict[str, str], status: int = 200) -> None:
        self.payload = body
        self.headers = headers
        self.status = status
        self.ok = status == 200

    async def body(self) -> bytes:
        return self.payload

    async def dispose(self) -> None:
        pass


class Request:
    def __init__(self, responses: dict[str, Response]) -> None:
        self.responses = responses
        self.calls: list[str] = []

    async def get(self, url: str, **kwargs: Any) -> Response:
        assert kwargs["max_redirects"] == 0
        self.calls.append(url)
        return self.responses[url]


@pytest.mark.parametrize("url", [
    "https://evil.test/pluginfile.php/a.pdf",
    BASE + "login/index.php", BASE + "mod/quiz/view.php?id=1",
    "http://econ.elearning.ubbcluj.ro/moodle/pluginfile.php/a.pdf",
])
def test_only_same_origin_material_gets(url: str) -> None:
    assert not allowed_material_url(url, RESOURCE)


def test_filename_preserves_unicode_extension_and_sanitizes_path() -> None:
    assert attachment_filename({"content-disposition": "attachment; filename*=UTF-8''Analiz%C4%83.pdf"}, RESOURCE, b"%PDF-1") == "Analiză.pdf"
    assert "/" not in attachment_filename({"content-disposition": 'attachment; filename="../../x.pdf"'}, RESOURCE, b"%PDF-1")
    assert attachment_filename({}, RESOURCE, b"Rar!123") == "Material.rar"
    assert attachment_filename({"content-disposition": 'attachment; filename="Cont de profit È\x99i pierdere.pdf"'}, RESOURCE, b"%PDF-1") == "Cont de profit și pierdere.pdf"


async def test_wrapper_downloads_real_file_not_html(tmp_path: Path) -> None:
    request = Request({
        RESOURCE: Response(f'<object data="{PDF}"></object><a href="{PDF}?forcedownload=1">Download</a><a href="{BASE}mod/resource/view.php?id=99">Next activity</a>'.encode(), {"content-type": "text/html"}),
        PDF: Response(b"%PDF-1.7 content", {"content-type": "application/pdf"}),
    })
    files, errors = await download_material(request, RESOURCE, tmp_path)
    assert not errors
    assert len(files) == 1
    assert files[0]["name"] == "lecture.pdf"
    assert Path(files[0]["downloaded_path"]).read_bytes().startswith(b"%PDF-")
    again, _ = await download_material(request, RESOURCE, tmp_path)
    assert files == again
    assert len(list(tmp_path.rglob("*.pdf"))) == 1


async def test_folder_downloads_multiple_files(tmp_path: Path) -> None:
    folder = BASE + "mod/folder/view.php?id=4"
    second = PDF.replace("lecture.pdf", "seminar.docx")
    request = Request({
        folder: Response(f'<a href="{PDF}">PDF</a><a href="{second}">Word</a>'.encode(), {"content-type": "text/html"}),
        PDF: Response(b"%PDF-1", {}),
        second: Response(b"PK\x03\x04word", {}),
    })
    files, errors = await download_material(request, folder, tmp_path)
    assert not errors
    assert {f["name"] for f in files} == {"lecture.pdf", "seminar.docx"}


async def test_login_html_is_not_saved_even_with_octet_stream(tmp_path: Path) -> None:
    request = Request({RESOURCE: Response(b"<!DOCTYPE html><html>Login</html>", {"content-type": "application/octet-stream"})})
    files, errors = await download_material(request, RESOURCE, tmp_path)
    assert not files and errors
    assert not list(tmp_path.iterdir())


async def test_redirect_never_requests_login_or_external_host(tmp_path: Path) -> None:
    request = Request({RESOURCE: Response(b"", {"location": "https://evil.test/pluginfile.php/x"}, 302)})
    files, errors = await download_material(request, RESOURCE, tmp_path)
    assert not files and errors
    assert request.calls == [RESOURCE]


def test_parser_selects_resource_not_section_navigation() -> None:
    html = f'<li class="section"><h3>Curs</h3><div class="activity modtype_resource"><a href="/moodle/course/view.php?id=1">Back</a><a href="{RESOURCE}">Lecture</a></div></li>'
    items = parse_course_html(html, BASE + "course/view.php?id=1")["sections"][0]["items"]
    assert len(items) == 1
    assert items[0]["file_url"] == RESOURCE


def test_section_summaries_are_opened_without_assessments_or_foreign_courses() -> None:
    course = BASE + "course/view.php?id=9738"
    html = f'''<li class="section main section-summary"><h3><a href="{course}&amp;section=4">Tematică C3/S3</a></h3></li>
    <li class="section-summary"><h3><a href="{course}&amp;section=9">Evaluare intermediară</a></h3></li>
    <li class="section-summary"><h3><a href="https://evil.test/course/view.php?id=9738&amp;section=4">Curs</a></h3></li>
    <li class="section-summary"><h3><a href="{BASE}course/view.php?id=2&amp;section=4">Alt curs</a></h3></li>'''
    assert parse_section_links(html, course) == [{"title": "Tematică C3/S3", "url": course + "&section=4"}]


def test_vault_has_real_files_local_links_and_keeps_user_notes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "vault/05 University"
    downloads = tmp_path / "downloads"
    downloads.mkdir()
    source = downloads / "lecture.pdf"
    source.write_bytes(b"%PDF-1")
    monkeypatch.setenv("MOODLE_OBSIDIAN_ROOT", str(root))
    monkeypatch.setenv("MOODLE_BRIDGE_OUTPUT_DIR", str(downloads))
    course = {"course": "Analiză financiară_EG3_26-27", "sections": [{"title": "C1/S1", "items": [{"item_type": "file", "title": "Lecture", "attachments": [{"downloaded_path": str(source)}]}]}]}
    _save_to_vault(course)
    index = root / "Analiză financiară/Săptămâna 1/C1-S1.md"
    assert "lecture.pdf|lecture.pdf]]" in index.read_text()
    index.write_text(index.read_text() + "\nNotițele mele personale\n")
    _save_to_vault(course)
    assert "Notițele mele personale" in index.read_text()
    assert len(list(root.rglob("*.pdf"))) == 1
    assert index.read_text().count("LORA:MOODLE:START") == 1
    # A modified file of the same name is preserved instead of overwritten.
    target = next(root.rglob("*.pdf"))
    target.write_bytes(b"manual edit")
    _save_to_vault(course)
    assert target.read_bytes() == b"manual edit"
    assert len(list(root.rglob("*.pdf"))) == 2


def test_unmarked_legacy_note_kept(tmp_path: Path) -> None:
    note = tmp_path / "Material.md"
    note.write_text("Conținutul meu")
    _write_generated(note, "Fișiere locale")
    _write_generated(note, "Fișiere locale actualizate")
    assert "Conținutul meu" in note.read_text()
    assert note.read_text().count("LORA:MOODLE:START") == 1
