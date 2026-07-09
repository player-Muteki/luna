from __future__ import annotations

from pathlib import Path
from unittest.mock import PropertyMock

from core.generator import NO_RESULT_MESSAGE, RAGGenerator

from .conftest import FakeLLM, EmptyLLM, StreamingLLM, build_retrieval_results


def test_generate_returns_no_result_without_context(tmp_path: Path) -> None:
    config, results = build_retrieval_results(tmp_path, query="nonexistent-token")
    generator = RAGGenerator(config, llm=FakeLLM())

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
    config, results = build_retrieval_results(tmp_path)
    generator = RAGGenerator(config, llm=FakeLLM())
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


def test_build_messages_low_confidence_uses_instructions_tag(tmp_path: Path) -> None:
    """Low confidence should appear in <instructions> tag, not inside <context>."""
    config, results = build_retrieval_results(tmp_path)
    generator = RAGGenerator(config, llm=FakeLLM())

    # Force low confidence
    results.results[0].final_score = 0.1
    type(results).confidence = PropertyMock(return_value="low")

    messages = generator.build_messages("retrieval 是什么？", results)

    context_section = messages[1]["content"]
    assert "<instructions>" in context_section
    assert "检索结果相关性较低" in context_section
    # Verify instructions come before context, not inside it
    instr_index = context_section.index("<instructions>")
    context_index = context_section.index("<context>")
    assert instr_index < context_index, "<instructions> should precede <context>"


def test_extract_references_returns_chunk_metadata(tmp_path: Path) -> None:
    config, results = build_retrieval_results(tmp_path)
    generator = RAGGenerator(config, llm=FakeLLM())

    references = generator.extract_references(results)

    assert references
    assert references[0].source_path.endswith("retrieval.md") or references[0].source_path.endswith("generator.md")
    assert references[0].chunk_id
    assert references[0].snippet


def test_generate_uses_llm_and_preserves_references(tmp_path: Path) -> None:
    config, results = build_retrieval_results(tmp_path)
    generator = RAGGenerator(config, llm=FakeLLM())

    generation = generator.generate("retrieval", results)

    assert "回答基于检索上下文" in generation.answer
    assert generation.finish_reason == "stop"
    assert generation.references
    assert generation.confidence in {"low", "medium", "high"}


def test_stream_generate_with_fake_llm_produces_answer(tmp_path: Path) -> None:
    config, results = build_retrieval_results(tmp_path)
    generator = RAGGenerator(config, llm=FakeLLM())

    chunks = list(generator.stream_generate("retrieval", results))

    assert len(chunks) == 1
    event_type, content = chunks[0]
    assert event_type == "content"
    assert "回答基于检索上下文" in content


def test_stream_generate_yields_stream_chunks(tmp_path: Path) -> None:
    config, results = build_retrieval_results(tmp_path)
    generator = RAGGenerator(config, llm=StreamingLLM())

    chunks = list(generator.stream_generate("retrieval", results))

    assert chunks == [("content", "第一段"), ("content", "第二段")]


def test_generate_returns_friendly_error_for_empty_response(tmp_path: Path) -> None:
    config, results = build_retrieval_results(tmp_path)
    generator = RAGGenerator(config, llm=EmptyLLM())

    generation = generator.generate("retrieval", results)

    assert generation.finish_reason == "error"
    assert "模型没有返回有效内容" in generation.answer
