from __future__ import annotations

from pathlib import Path

from app.ingest import IngestionEngine
from app.retriever import HybridRetriever
from config import ensure_directories, load_settings

from .conftest import FakeEmbeddingModel, make_settings


def build_engine_and_retriever(tmp_path: Path):
    settings = make_settings(tmp_path)
    embedding_model = FakeEmbeddingModel()
    engine = IngestionEngine(settings, embedding_model=embedding_model)

    (settings.data_dir / "retrieval.md").write_text(
        "Hybrid retrieval combines vector retrieval with BM25 for better recall.",
        encoding="utf-8",
    )
    (settings.data_dir / "generator.md").write_text(
        "The generator builds answers from retrieved context and cites sources.",
        encoding="utf-8",
    )
    (settings.data_dir / "config.txt").write_text(
        "TOP_K controls how many retrieved chunks are passed into the prompt.",
        encoding="utf-8",
    )

    engine.add_files(engine.scan_files())
    retriever = HybridRetriever(settings, engine.vector_store, embedding_model=embedding_model)
    return settings, engine, retriever


def test_vector_retrieve_returns_semantic_match(tmp_path: Path) -> None:
    _, _, retriever = build_engine_and_retriever(tmp_path)

    results = retriever.retrieve("Explain retrieval", mode="vector")

    assert results.results
    assert results.results[0].file_name == "retrieval.md"
    assert "vector" in results.results[0].matched_by


def test_bm25_retrieve_finds_exact_symbol_terms(tmp_path: Path) -> None:
    _, _, retriever = build_engine_and_retriever(tmp_path)

    results = retriever.retrieve("TOP_K", mode="bm25")

    assert results.results
    assert results.results[0].file_name == "config.txt"
    assert results.results[0].bm25_score is not None


def test_bm25_idf_cache_reuses_on_same_data(tmp_path: Path) -> None:
    _, _, retriever = build_engine_and_retriever(tmp_path)

    # First call builds the cache
    results1 = retriever.retrieve("retrieval", mode="bm25")
    n_after_first = retriever._idf_n

    # Second call should reuse cache
    results2 = retriever.retrieve("retrieval", mode="bm25")
    assert retriever._idf_n == n_after_first
    assert retriever._idf_cache is not None
    assert results1.results
    assert results2.results


def test_bm25_idf_cache_invalidate_forces_rebuild(tmp_path: Path) -> None:
    _, _, retriever = build_engine_and_retriever(tmp_path)

    retriever.retrieve("retrieval", mode="bm25")
    retriever.invalidate_idf_cache()

    assert retriever._idf_cache is None
    assert retriever._idf_n == 0

    # Rebuild on next call
    retriever.retrieve("retrieval", mode="bm25")
    assert retriever._idf_cache is not None


def test_hybrid_fusion_deduplicates_same_chunk(tmp_path: Path) -> None:
    _, _, retriever = build_engine_and_retriever(tmp_path)

    results = retriever.retrieve("retrieval", mode="hybrid")

    chunk_ids = [item.chunk_id for item in results.results]
    assert len(chunk_ids) == len(set(chunk_ids))
    assert any(set(item.matched_by) == {"vector", "bm25"} for item in results.results)


def test_history_short_query_expands_effective_query(tmp_path: Path) -> None:
    _, _, retriever = build_engine_and_retriever(tmp_path)
    history = [
        {"role": "user", "content": "介绍一下 retrieval 模块"},
        {"role": "assistant", "content": "..."},
    ]

    results = retriever.retrieve("它有哪些优点？", chat_history=history, mode="hybrid")

    assert results.effective_query.startswith("介绍一下 retrieval 模块")


def test_context_text_contains_source_and_chunk_id(tmp_path: Path) -> None:
    _, _, retriever = build_engine_and_retriever(tmp_path)

    results = retriever.retrieve("generator", mode="hybrid")
    context = results.to_context_text(token_budget=500)

    assert "source:" in context
    assert "chunk_id:" in context
    assert "content:" in context
