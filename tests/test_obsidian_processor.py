from pathlib import Path
import zipfile

import pytest

from integrations import obsidian_processor


@pytest.mark.asyncio
async def test_private_note_is_not_analyzed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    note = vault / "journal.md"
    note.write_text("---\nprivate: true\n---\n\nUn jurnal suficient de lung pentru test.", encoding="utf-8")
    monkeypatch.setattr(obsidian_processor, "VAULT_PATH", vault)
    monkeypatch.setattr(obsidian_processor, "STATE_PATH", vault / ".lora" / "processed.json")
    monkeypatch.setattr(obsidian_processor, "ANALYSIS_DIR", vault / ".lora" / "analysis")

    result = await obsidian_processor.process_vault()

    assert result["processed"] == 0
    assert result["skipped"] == 1
    assert not (vault / ".lora" / "analysis" / "journal.analysis.md").exists()


@pytest.mark.asyncio
async def test_small_note_is_skipped_without_calling_model(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "short.md").write_text("idee", encoding="utf-8")
    monkeypatch.setattr(obsidian_processor, "VAULT_PATH", vault)
    monkeypatch.setattr(obsidian_processor, "STATE_PATH", vault / ".lora" / "processed.json")
    monkeypatch.setattr(obsidian_processor, "ANALYSIS_DIR", vault / ".lora" / "analysis")

    result = await obsidian_processor.process_vault()

    assert result == {"processed": 0, "skipped": 1}


def test_pptx_xml_extraction_without_optional_python_pptx(tmp_path: Path) -> None:
    deck = tmp_path / "curs.pptx"
    xml = """<p:sld xmlns:p=\"urn:p\" xmlns:a=\"urn:a\"><a:t>Definitia bazei de date</a:t><a:t>Exemplu SQL</a:t></p:sld>"""
    with zipfile.ZipFile(deck, "w") as archive:
        archive.writestr("ppt/slides/slide1.xml", xml)

    extracted = obsidian_processor._extract_presentation_text(deck)

    assert "Definitia bazei de date" in extracted
    assert "Exemplu SQL" in extracted


def test_docx_xml_extraction(tmp_path: Path) -> None:
    document = tmp_path / "curs.docx"
    xml = """<w:document xmlns:w=\"urn:w\"><w:body><w:p><w:r><w:t>Capitolul unu</w:t></w:r></w:p><w:p><w:r><w:t>Idee importanta</w:t></w:r></w:p></w:body></w:document>"""
    with zipfile.ZipFile(document, "w") as archive:
        archive.writestr("word/document.xml", xml)

    extracted = obsidian_processor._extract_docx_text(document)

    assert extracted == "Capitolul unu\n\nIdee importanta"


def test_build_study_index_groups_resources_and_outputs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    vault = tmp_path / "vault"
    section = vault / "05 University" / "Subjects" / "Analiză financiară" / "Cursuri"
    (section / "Resources").mkdir(parents=True)
    (section / "Lora" / "Summaries").mkdir(parents=True)
    (section / "Lora" / "Summaries" / "capitol-1.summary.md").write_text("summary", encoding="utf-8")
    (section / "Resources" / "capitol-1.pdf").write_bytes(b"pdf")
    (section / "Notițe.md").write_text("notiță", encoding="utf-8")
    monkeypatch.setattr(obsidian_processor, "VAULT_PATH", vault)

    assert obsidian_processor.build_study_indexes() == 1
    index = vault / "05 University" / "Subjects" / "Analiză financiară" / "Lora" / "Study Index.md"
    content = index.read_text(encoding="utf-8")
    assert "Resources" in content
    assert "capitol-1" in content
    assert "capitol-1.summary" in content
    assert "Notițe" in content


def test_build_inbox_status_lists_new_document(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    vault = tmp_path / "vault"
    inbox = vault / "07 Notes" / "Inbox"
    inbox.mkdir(parents=True)
    (inbox / "Baze de date - curs.pdf").write_bytes(b"pdf")
    subjects = vault / "05 University" / "Subjects" / "Baze de date"
    subjects.mkdir(parents=True)
    monkeypatch.setattr(obsidian_processor, "VAULT_PATH", vault)
    monkeypatch.setattr(obsidian_processor, "STATE_PATH", vault / ".lora" / "processed.json")

    obsidian_processor.build_inbox_status()

    content = (inbox / "_Processing Status.md").read_text(encoding="utf-8")
    assert "Baze de date - curs" in content
    assert "Necesită alegerea materiei" not in content
    assert "nou" in content


def test_build_review_dashboard_contains_local_queries(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    vault = tmp_path / "vault"
    monkeypatch.setattr(obsidian_processor, "VAULT_PATH", vault)

    obsidian_processor.build_review_dashboard()

    content = (vault / "00 Dashboard" / "Review.md").read_text(encoding="utf-8")
    assert "Review zilnic" in content
    assert 'FROM "05 University/Subjects"' in content
    assert "flashcards" in content
    assert "Examene apropiate" in content


def test_move_inbox_document_requires_valid_subject_and_type(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    vault = tmp_path / "vault"
    inbox = vault / "07 Notes" / "Inbox"
    inbox.mkdir(parents=True)
    (inbox / "curs.pdf").write_bytes(b"pdf")
    subject = vault / "05 University" / "Subjects" / "Baze de date"
    subject.mkdir(parents=True)
    monkeypatch.setattr(obsidian_processor, "VAULT_PATH", vault)

    moved = obsidian_processor.move_inbox_document(
        "07 Notes/Inbox/curs.pdf", "Baze de date", "Cursuri"
    )

    assert moved.endswith("Cursuri/Resources/curs.pdf")
    assert not (inbox / "curs.pdf").exists()
