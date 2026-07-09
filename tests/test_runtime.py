"""
Runtime module 测试 — WorkspaceRuntime seam。

覆盖：
  - bootstrap() 基本冒烟
  - ask() 从空索引 → 自动索引 → 检索 → 生成的完整流程
  - ask() 无文件时的边界情况
  - 向后兼容委托属性
  - get_project_info() / get_stats()
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from core.runtime import WorkspaceRuntime, AskResult

from tests.conftest import make_runtime


# ═══════════════════════════════════════════════════════════════════
#  bootstrap
# ═══════════════════════════════════════════════════════════════════


class TestBootstrap:
    def test_bootstrap_creates_co_dir(self, tmp_path: Path) -> None:
        cwd = tmp_path / "ws"
        cwd.mkdir()
        runtime = WorkspaceRuntime.bootstrap(str(cwd))
        assert runtime.root == cwd.resolve()
        assert (cwd / ".co-thinker").exists()
        assert (cwd / ".co-thinker" / "vectordb").exists()


# ═══════════════════════════════════════════════════════════════════
#  ask()
# ═══════════════════════════════════════════════════════════════════


class TestAsk:
    def test_ask_auto_indexes_and_generates(self, tmp_path: Path) -> None:
        """空索引 → 扫描文件 → 索引 → 检索 → 生成。"""
        runtime = make_runtime(tmp_path)

        # 写一个可索引的文件
        (tmp_path / "readme.md").write_text(
            "# Test\nHybrid retrieval combines vector with BM25.", encoding="utf-8"
        )

        result = runtime.ask("retrieval")

        assert isinstance(result, AskResult)
        assert result.indexed_file_count == 1
        assert result.indexed_chunk_count > 0
        assert len(result.references) > 0
        # 答案不为空（假 LLM 返回固定字符串）
        assert result.answer

    def test_ask_no_files_returns_empty(self, tmp_path: Path) -> None:
        """没有可索引文件时，返回空但不会崩溃。"""
        runtime = make_runtime(tmp_path)

        result = runtime.ask("anything")

        assert isinstance(result, AskResult)
        assert result.indexed_file_count == 0
        assert len(result.references) == 0
        # Generator 即使无检索也会返回提示消息
        assert result.answer

    def test_ask_preexisting_index(self, tmp_path: Path) -> None:
        """已有索引时不重复索引。"""
        (tmp_path / "doc.md").write_text("# Doc\nContent about generators.", encoding="utf-8")

        runtime = make_runtime(tmp_path)

        # 第一次调用：会索引
        first = runtime.ask("generator")
        assert first.indexed_file_count == 1

        # 第二次调用：已有索引，不应重新索引
        second = runtime.ask("generator")
        assert second.indexed_file_count == 0  # 不需要索引
        assert len(second.references) > 0
        assert second.answer

    def test_ask_confidence_and_references(self, tmp_path: Path) -> None:
        """AskResult 包含 confidence 与 references。"""
        (tmp_path / "doc.md").write_text("# Doc\nContent about retrieval.", encoding="utf-8")

        runtime = make_runtime(tmp_path)
        result = runtime.ask("retrieval")

        assert result.confidence in ("high", "medium", "low", "none")
        if result.references:
            ref = result.references[0]
            assert "source_path" in ref
            assert "score" in ref


# ═══════════════════════════════════════════════════════════════════
#  向后兼容委托属性
# ═══════════════════════════════════════════════════════════════════


class TestDelegation:
    def test_engine_properties(self, tmp_path: Path) -> None:
        runtime = make_runtime(tmp_path)

        assert runtime.llm is not None
        assert runtime.vectorstore is not None
        assert runtime.ingest_engine is not None
        assert runtime.retriever is not None
        assert runtime.generator is not None
        assert runtime.chat_engine is not None
        assert runtime.manifest is not None
        assert runtime.config is not None
        assert runtime.root == tmp_path.resolve()

    def test_scan_files_delegation(self, tmp_path: Path) -> None:
        runtime = make_runtime(tmp_path)

        (tmp_path / "guide.md").write_text("# Guide", encoding="utf-8")
        files = runtime.scan_files()
        paths = [f["path"] for f in files if not f["is_dir"]]
        assert "guide.md" in paths


# ═══════════════════════════════════════════════════════════════════
#  信息接口
# ═══════════════════════════════════════════════════════════════════


class TestInfo:
    def test_get_project_info(self, tmp_path: Path) -> None:
        runtime = make_runtime(tmp_path)

        info = runtime.get_project_info()
        assert info["root"] == str(tmp_path.resolve())
        assert "name" in info
        assert "config" in info
        assert "stats" in info

    def test_get_stats(self, tmp_path: Path) -> None:
        runtime = make_runtime(tmp_path)

        stats = runtime.get_stats()
        assert "document_count" in stats
        assert "chunk_count" in stats
