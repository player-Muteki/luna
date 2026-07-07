from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from app.ingest import IngestionEngine
from app.retriever import HybridRetriever
from config import ensure_directories, load_settings


# ── Fake embedding model ──────────────────────────────────────────

class FakeEmbeddingModel:
    """Deterministic embedding for tests: checks keyword presence in each dim."""

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


# ── Mock LLM infrastructure ───────────────────────────────────────

class _Message:
    def __init__(self, content: str) -> None:
        self.content = content


class _Delta:
    def __init__(self, content: str) -> None:
        self.content = content


class _Choice:
    """Mock a single chat completion choice."""

    def __init__(self, content: str, for_stream: bool = False) -> None:
        if for_stream:
            self.delta = _Delta(content)
        else:
            self.message = _Message(content)


class _Response:
    """Mock a non-streaming response."""

    def __init__(self, content: str) -> None:
        self.choices = [_Choice(content)]


class _Chunk:
    """Mock a streaming chunk — only delta, no message."""

    def __init__(self, content: str) -> None:
        self.choices = [_Choice(content, for_stream=True)]


class _Completions:
    """Mock llm.chat.completions — matches openai's chat.completions.create()."""

    def __init__(self, sync_response: str, stream_chunks: list[_Chunk] | None = None) -> None:
        self._sync_response = sync_response
        self._stream_chunks = stream_chunks

    def create(
        self,
        model: str | None = None,
        messages: list[dict[str, str]] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        stream: bool = False,
    ) -> Any:
        if stream:
            return iter(self._stream_chunks or [_Chunk("")])
        return _Response(self._sync_response)


class _Chat:
    """Mock llm.chat — provides .completions.create() matching openai SDK path."""

    def __init__(self, sync_response: str = "", stream_chunks: list[_Chunk] | None = None) -> None:
        self.completions = _Completions(sync_response, stream_chunks)


def _make_chat(sync: str, stream: list[_Chunk] | None = None) -> _Chat:
    return _Chat(sync_response=sync, stream_chunks=stream or [_Chunk(sync)])


class FakeLLM:
    """LLM mock that returns a fixed answer (non-streaming and streaming)."""

    def __init__(self) -> None:
        self.chat = _make_chat(
            sync="回答基于检索上下文。[1]\n\n引用来源：\n[1] unknown",
            stream=[_Chunk("回答基于检索上下文。[1]\n\n引用来源：\n[1] unknown")],
        )


class EmptyLLM:
    """LLM mock that returns empty content."""

    def __init__(self) -> None:
        self.chat = _make_chat(sync="")


class StreamingLLM:
    """LLM mock that yields multiple stream chunks."""

    def __init__(self) -> None:
        self.chat = _make_chat(
            sync="第一段第二段",
            stream=[_Chunk("第一段"), _Chunk("第二段")],
        )


# ── Test helpers ──────────────────────────────────────────────────

def make_settings(tmp_path: Path, **overrides: Any) -> Any:
    """Create a Settings instance with sensible test defaults."""
    defaults: dict[str, Any] = {
        "data_dir": tmp_path / "data",
        "vectorstore_dir": tmp_path / "vectorstore",
        "storage_dir": tmp_path / "storage",
        "chunk_size": 400,
        "chunk_overlap": 20,
        "top_k": 5,
        "retrieval_candidate_k": 10,
        "similarity_cutoff": 0.0,
        "deepseek_api_key": "sk-test-key",
    }
    defaults.update(overrides)
    settings = load_settings(overrides=defaults)
    ensure_directories(settings)
    return settings


def build_retrieval_results(
    tmp_path: Path,
    query: str = "retrieval",
) -> tuple[Any, Any]:
    """Ingest two test documents and return (settings, retrieval_results)."""
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

    engine.add_files(engine.scan_files())
    retriever = HybridRetriever(settings, engine.vector_store, embedding_model=embedding_model)
    results = retriever.retrieve(query, mode="hybrid")
    return settings, results
