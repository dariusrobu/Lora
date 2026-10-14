from pathlib import Path

import pytest

from scripts.moodle_bridge import _save_to_vault


def test_financial_sections_stay_in_their_numbered_weeks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    vault = tmp_path / "vault"
    root = vault / "05 University"
    downloads = tmp_path / "downloads"
    downloads.mkdir()
    monkeypatch.setenv("MOODLE_OBSIDIAN_ROOT", str(root))
    monkeypatch.setenv("MOODLE_BRIDGE_OUTPUT_DIR", str(downloads))
    course = {"course": "Analiză financiară_EG3_26-27", "sections": []}
    for number in (1, 10, 11, 12, 13, 14):
        source = downloads / f"curs{number}.pdf"
        source.write_bytes(f"%PDF-curs{number}".encode())
        course["sections"].append({
            "title": f"Tematică C{number}/S{number}",
            "items": [{"item_type": "file", "title": source.name,
                       "attachments": [{"downloaded_path": str(source)}]}],
        })
    _save_to_vault(course)
    _save_to_vault(course)
    subject = root / "Analiză financiară"
    for number in (1, 10, 11, 12, 13, 14):
        week = subject / f"Săptămâna {number}"
        assert (week / "Curs").is_dir()
        assert (week / "Seminar").is_dir()
        assert [path.name for path in (week / "Files").iterdir()] == [f"curs{number}.pdf"]
        note = week / f"Tematică C{number}-S{number}.md"
        attachment = week / "Files" / f"curs{number}.pdf"
        assert f"[[{attachment.relative_to(vault).as_posix()}|" in note.read_text()
    assert not list(subject.rglob("Files - *"))
    assert not list((subject / "Săptămâna 1").glob("Tematică C1[0-4]*"))
