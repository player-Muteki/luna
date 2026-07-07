from __future__ import annotations

from pathlib import Path

from app.generator import NO_RESULT_MESSAGE, RAGGenerator
from app.ingest import IngestionEngine
from app.retriever import HybridRetriever
from config import ensure_directories, load_settings


class FakeEmbeddingModel:
    def get_text_embedding_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.get_text_embedding(text) for text in texts]

    def get_text_embedding(self, text: str) -> list[float]:
        text = text.lower()
        return [
            1.0 if "retrieval" in text else 0.0,
            1.0 if "generator" in text else 0.0,
            1.0 if "config" in text else 0.0,
        ]

    def get_query_embedding(self, query: str) -> list[float]:
        return self.get_text_embedding(query)


class _Choice:
    """Mock a single chat completion choice."""
    def __init__(self, content: str):
        self.message = _Message(content)
        self.delta = _Delta(content)


class _Message:
    def __init__(self, content: str):
        self.content = content


class _Delta:
    def __init__(self, content: str):
        self.content = content


class _Chunk:
    """Mock a streaming chunk."""
    def __init__(self, content: str):
        self.choices = [_Choice(content)]


class _Response:
    """Mock a non-streaming response."""
    def __init__(self, content: str):
        self.choices = [_Choice(content)]


class _Chat:
    """Mock llm.chat — provides .completions.create() matching openai SDK path."""

    def __init__(self, sync_response: str = "", stream_chunks: list[_Chunk] | None = None):
        self.completions = _Completions(sync_response, stream_chunks)


class _Completions:
    """Mock llm.chat.completions — matches openai's chat.completions.create()."""

    def __init__(self, sync_response: str, stream_chunks: list[_Chunk] | None = None):
        self._sync_response = sync_response
        self._stream_chunks = stream_chunks

    def create(self, model=None, messages=None, temperature=None, max_tokens=None, stream=False):
        if stream:
            return iter(self._stream_chunks or [_Chunk("")])
        return _Response(self._sync_response)


def _make_chat(sync: str, stream: list[_Chunk] | None = None) -> _Chat:
    return _Chat(sync_response=sync, stream_chunks=stream or [_Chunk(sync)])


class FakeLLM:
    def __init__(self):
        self.chat = _make_chat(
            sync="回答基于检索上下文。[1]\n\n引用来源：\n[1] unknown",
            stream=[_Chunk("回答基于检索上下文。[1]\n\n引用来源：\n[1] unknown")],
        )


class EmptyLLM:
    def __init__(self):
        self.chat = _make_chat(sync="")


class StreamingLLM:
    def __init__(self):
        self.chat = _make_chat(
            sync="第一段第二段",
            stream=[_Chunk("第一段"), _Chunk("第二段")],
        )


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
            "deepseek_api_key": "sk-test-key",
        }
    )
    ensure_directories(settings)
    return settings


def build_retrieval_results(tmp_path: Path, query: str = "retrieval"):
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


def test_generate_returns_no_result_without_context(tmp_path: Path) -> None:
    settings, results = build_retrieval_results(tmp_path, query="nonexistent-token")
    generator = RAGGenerator(settings, llm=FakeLLM())

    empty_results = results.__class__(
        original_query="missing",
        effective_query="missing",
        results=[],
        mode="hybrid",
        total_candidates=0,
        elapsed_ms=0.0,
    )
    generation = generator.generate("missing", empty_results)

    assert generation.answer == NO_RESULT_MESSAGE
    assert generation.finish_reason == "no_context"
    assert generation.references == []


def test_build_messages_includes_context_history_and_question(tmp_path: Path) -> None:
    settings, results = build_retrieval_results(tmp_path)
    generator = RAGGenerator(settings, llm=FakeLLM())
    history = [
        {"role": "user", "content": "先介绍一下 retrieval"},
        {"role": "assistant", "content": "好的"},
    ]

    messages = generator.build_messages("retrieval 是什么？", results, history)

    assert messages[0]["role"] == "system"
    assert "<context>" in messages[1]["content"]
    assert "<chat_history>" in messages[1]["content"]
    assert "retrieval 是什么？" in messages[1]["content"]
    assert "用户: 先介绍一下 retrieval" in messages[1]["content"]


def test_extract_references_returns_chunk_metadata(tmp_path: Path) -> None:
    settings, results = build_retrieval_results(tmp_path)
    generator = RAGGenerator(settings, llm=FakeLLM())

    references = generator.extract_references(results)

    assert references
    assert references[0].source_path.endswith("retrieval.md") or references[0].source_path.endswith("generator.md")
    assert references[0].chunk_id
    assert references[0].snippet


def test_generate_uses_llm_and_preserves_references(tmp_path: Path) -> None:
    settings, results = build_retrieval_results(tmp_path)
    generator = RAGGenerator(settings, llm=FakeLLM())

    generation = generator.generate("retrieval", results)

    assert "回答基于检索上下文" in generation.answer
    assert generation.finish_reason == "stop"
    assert generation.references
    assert generation.confidence in {"low", "medium", "high"}


def test_stream_generate_with_fake_llm_produces_answer(tmp_path: Path) -> None:
    settings, results = build_retrieval_results(tmp_path)
    generator = RAGGenerator(settings, llm=FakeLLM())

    chunks = list(generator.stream_generate("retrieval", results))

    assert len(chunks) == 1
    assert "回答基于检索上下文" in chunks[0]


def test_stream_generate_yields_stream_chunks(tmp_path: Path) -> None:
    settings, results = build_retrieval_results(tmp_path)
    generator = RAGGenerator(settings, llm=StreamingLLM())

    chunks = list(generator.stream_generate("retrieval", results))

    assert chunks == ["第一段", "第二段"]


def test_generate_returns_friendly_error_for_empty_response(tmp_path: Path) -> None:
    settings, results = build_retrieval_results(tmp_path)
    generator = RAGGenerator(settings, llm=EmptyLLM())

    generation = generator.generate("retrieval", results)

    assert generation.finish_reason == "error"
    assert "模型没有返回有效内容" in generation.answer
