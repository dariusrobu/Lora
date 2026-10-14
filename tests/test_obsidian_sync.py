from pathlib import Path

import integrations.obsidian_sync as obsidian


def test_write_note_is_idempotent_and_preserves_manual_content(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(obsidian, "VAULT_PATH", tmp_path.resolve())
    fields = {"type": "task", "lora_id": 7, "status": "pending"}
    assert obsidian._write_note("02 Tasks/Test [7].md", fields, "# Test\n\nGenerated")
    path = tmp_path / "02 Tasks" / "Test [7].md"
    path.write_text(path.read_text() + "\nManual note\n", encoding="utf-8")

    assert obsidian._write_note("02 Tasks/Test [7].md", {**fields, "status": "done"}, "# Test\n\nGenerated")
    content = path.read_text(encoding="utf-8")
    assert 'status: "done"' in content
    assert "Manual note" in content
    assert not obsidian._write_note("02 Tasks/Test [7].md", {**fields, "status": "done"}, "# Test\n\nGenerated")


def test_write_note_rejects_path_escape(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(obsidian, "VAULT_PATH", tmp_path.resolve())
    try:
        obsidian._write_note("../outside.md", {"type": "task"}, "# nope")
    except ValueError as exc:
        assert "escaped" in str(exc)
    else:
        raise AssertionError("path traversal was not rejected")
