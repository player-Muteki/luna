from __future__ import annotations

import json

from core.ingest import IngestionEngine

from .conftest import make_project_config


def test_scan_files_filters_hidden_and_supported_extensions(tmp_path: Path) -> None:
    config = make_project_config(tmp_path)
    (tmp_path / "guide.md").write_text("# Guide\nhello", encoding="utf-8")
    (tmp_path / "notes.bin").write_text("ignored", encoding="utf-8")
    hidden_dir = tmp_path / ".hidden"
    hidden_dir.mkdir()
    (hidden_dir / "secret.md").write_text("hidden", encoding="utf-8")

    engine = IngestionEngine(config=config, root=tmp_path)
    files = engine.scan_files()

    assert files == [tmp_path / "guide.md"]


def test_add_files_indexes_and_deduplicates(tmp_path: Path) -> None:
    config = make_project_config(tmp_path, chunk_size=40, chunk_overlap=10)
    source = tmp_path / "guide.md"
    source.write_text("A" * 120, encoding="utf-8")

    engine = IngestionEngine(config=config, root=tmp_path)
    first = engine.add_files([source])
    second = engine.add_files([source])

    assert first.indexed_files == 1
    assert first.total_chunks >= 2
    assert second.skipped_files == 1
    assert engine.get_index_stats()["chunk_count"] == first.total_chunks


def test_add_files_replaces_chunks_when_file_changes(tmp_path: Path) -> None:
    config = make_project_config(tmp_path, chunk_size=40, chunk_overlap=10)
    source = tmp_path / "guide.md"
    source.write_text("A" * 120, encoding="utf-8")

    engine = IngestionEngine(config=config, root=tmp_path)
    initial = engine.add_files([source])
    source.write_text("B" * 20, encoding="utf-8")
    updated = engine.add_files([source])

    stats = engine.get_index_stats()
    manifest = json.loads(
        (tmp_path / ".co-thinker" / "vectordb" / "manifest.json").read_text(encoding="utf-8")
    )

    assert initial.indexed_files == 1
    assert updated.indexed_files == 1
    assert stats["chunk_count"] == 1
    assert len(manifest["documents"]) == 1


def test_delete_file_removes_manifest_and_chunks(tmp_path: Path) -> None:
    config = make_project_config(tmp_path, chunk_size=40, chunk_overlap=10)
    source = tmp_path / "guide.md"
    source.write_text("content for deletion test", encoding="utf-8")

    engine = IngestionEngine(config=config, root=tmp_path)
    summary = engine.add_files([source])
    document_id = summary.results[0].document_id

    result = engine.delete_file(document_id)

    assert result.status == "deleted"
    assert engine.get_index_stats()["chunk_count"] == 0
    assert engine.list_documents() == []


def test_add_pdf_file(tmp_path: Path) -> None:
    from tests.conftest import make_pdf_bytes

    config = make_project_config(tmp_path)
    source = tmp_path / "test.pdf"
    source.write_bytes(make_pdf_bytes("PDF test content " * 20))

    engine = IngestionEngine(config=config, root=tmp_path)
    summary = engine.add_files([source])

    assert summary.indexed_files == 1
    assert summary.total_chunks >= 1
    stats = engine.get_index_stats()
    assert stats["chunk_count"] >= 1
    assert stats["indexed_document_count"] >= 1


def test_add_docx_file(tmp_path: Path) -> None:
    from tests.conftest import make_docx_bytes

    config = make_project_config(tmp_path)
    source = tmp_path / "test.docx"
    source.write_bytes(make_docx_bytes("DOCX test content " * 20))

    engine = IngestionEngine(config=config, root=tmp_path)
    summary = engine.add_files([source])

    assert summary.indexed_files == 1
    assert summary.total_chunks >= 1
    stats = engine.get_index_stats()
    assert stats["chunk_count"] >= 1


def test_add_pptx_file(tmp_path: Path) -> None:
    from tests.conftest import make_pptx_bytes

    config = make_project_config(tmp_path)
    source = tmp_path / "test.pptx"
    source.write_bytes(make_pptx_bytes("PPTX test content " * 20))

    engine = IngestionEngine(config=config, root=tmp_path)
    summary = engine.add_files([source])

    assert summary.indexed_files == 1
    assert summary.total_chunks >= 1
    stats = engine.get_index_stats()
    assert stats["chunk_count"] >= 1
