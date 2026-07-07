from __future__ import annotations

from pathlib import Path

from app.ingest import IngestionEngine
from app.retriever import HybridRetriever
from config import ensure_directories, load_settings


class FakeEmbeddingModel:
    def get_text_embedding_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.get_text_embedding(text) for text in texts]

    def get_text_embedding(self, text: str) -> list[float]:
        text = text.lower()
        return [
            1.0 if "retrieval" in text or "检索" in text else 0.0,
            1.0 if "generator" in text or "生成" in text else 0.0,
            1.0 if "config" in text or "配置" in text else 0.0,
        ]

    def get_query_embedding(self, query: str) -> list[float]:
        return self.get_text_embedding(query)


def make_settings(tmp_path: Path):
    settings = load_settings(
        overrides={
            "data_dir": tmp_path / "data",
            "vectorstore_dir": tmp_path / "vectorstore",
            "storage_dir": tmp_path / "storage",
            "chunk_size": 400,
            "chunk_overlap": 20,
            "top_k": 5,
            "retrieval_candidate_k": 10,
            "similarity_cutoff": 0.0,
        }
    )
    ensure_directories(settings)
    return settings


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
