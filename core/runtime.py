"""
WorkspaceRuntime — Co-Thinker 运行时 module。

职责：
  1. 提供 WorkspaceRuntime.bootstrap() 作为统一出厂函数
     （替代 api/deps.py 和 cli.py 中重复的 bootstrap 逻辑）。
  2. 提供 CLI 使用的高层接口（ask / index_if_empty / get_stats）。
  3. 对现有 API route 提供向后兼容的委托属性（Phase 5 再逐步移除）。

使用方期望：
  - CLI:   runtime.ask(query) → AskResult
  - API:   runtime.xxx（通过委托属性访问内部引擎，Phase 5 再深化）
  - 测试： 用 mock 引擎构造 WorkspaceRuntime，不经过 bootstrap()。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ── CLI 查询结果类型 ─────────────────────────────────────────────────


@dataclass
class AskResult:
    """``ask()`` 返回的完整查询结果，供 CLI 展示。"""
    answer: str
    reasoning: str
    references: list[dict[str, Any]]
    confidence: str
    retrieval_details: dict[str, Any] | None = None
    indexed_file_count: int = 0
    indexed_chunk_count: int = 0


# ── WorkspaceRuntime ─────────────────────────────────────────────────


class WorkspaceRuntime:
    """绑定到一个工作目录的运行时能力。

    把 ProjectContext（工作目录 + 配置）与模型初始化、引擎组装
    封装在一起，对外暴露高层接口。
    """

    def __init__(self, ctx: Any):
        """通常通过 ``bootstrap()`` 构造，不应直接调用。"""
        self._ctx = ctx
    # ── 公开 ctx 属性 ────────────────────────────────────────────

    @property
    def ctx(self) -> Any:
        """公开 ProjectContext 引用，供 ChatWorkflow 等组件使用。

        替代直接访问 ``_runtime._ctx`` 的私有属性方式。
        """
        return self._ctx


    # ── 统一出厂 ────────────────────────────────────────────────────

    @classmethod
    def bootstrap(cls, explicit_root: str | None = None) -> WorkspaceRuntime:
        """加载工作目录、初始化模型、组装所有引擎——一次性完成。

        这是 deps.py 和 cli.py 中重复 bootstrap 逻辑的统一版本。
        """
        from core.project import ProjectContext, get_api_key, get_llm, get_embedding_model

        ctx = ProjectContext.load(explicit_root)

        # API Key（可能没有）
        if get_api_key(ctx):
            try:
                ctx.llm = get_llm(ctx)
            except Exception:
                pass

        # Embedding 模型（可能没有）
        ctx.embedding_model = get_embedding_model(ctx)

        # 组装引擎
        ctx.setup_engines()

        return cls(ctx)

    # ── 高层 CLI 接口 ──────────────────────────────────────────────

    def ask(self, query: str) -> AskResult:
        """非交互式 RAG 问答（CLI 模式）。

        自动处理：空索引 → 自动索引 → 检索 → 生成。
        不处理会话历史（单轮问答）。
        """
        # Step 1: 确保有索引
        summary = self._ensure_indexed()
        indexed_file_count = summary.indexed_files if summary else 0
        indexed_chunk_count = summary.total_chunks if summary else 0

        # Step 2: 检索
        results = self._ctx.retriever.retrieve(query=query)

        # Step 3: 收集检索详情
        retrieval_details = None
        if results.results:
            retrieval_details = {
                "mode": results.mode,
                "elapsed_ms": round(results.elapsed_ms, 1),
                "total_candidates": results.total_candidates,
                "effective_query": results.effective_query,
            }

        # Step 4: 流式生成 → 收集完整答案
        answer = ""
        reasoning = ""
        for event_type, content in self._ctx.generator.stream_generate(query, results):
            if event_type == "reasoning":
                reasoning += content
            else:
                answer += content

        return AskResult(
            answer=answer,
            reasoning=reasoning,
            references=results.to_sources()[:10],
            confidence=results.confidence,
            retrieval_details=retrieval_details,
            indexed_file_count=indexed_file_count,
            indexed_chunk_count=indexed_chunk_count,
        )

    # ── 内部工具 ──────────────────────────────────────────────────

    def _ensure_indexed(self) -> Any | None:
        """如果向量库为空，自动扫描并索引工作目录。"""
        if not self._ctx.vectorstore or self._ctx.vectorstore.count_chunks() == 0:
            files = self._ctx.ingest_engine.scan_files()
            if files:
                return self._ctx.ingest_engine.add_files(files)
        return None

    # ── 对外信息接口 ───────────────────────────────────────────────

    def get_project_info(self) -> dict[str, Any]:
        return self._ctx.get_project_info()

    def get_stats(self) -> dict[str, Any]:
        if self._ctx.ingest_engine:
            return self._ctx.ingest_engine.get_index_stats()
        return {"document_count": 0, "indexed_document_count": 0, "chunk_count": 0}

    # ── 向后兼容委托属性 ──────────────────────────────────────────
    #
    # 以下属性让现有 API route 在 Phase 5 之前可以继续通过
    # WorkspaceRuntime 访问内部引擎。Phase 5 将逐步移除这些委托，
    # 改为 route 只做 HTTP/WebSocket adapter。

    @property
    def llm(self) -> Any | None:
        return self._ctx.llm

    @property
    def vectorstore(self) -> Any | None:
        return self._ctx.vectorstore

    @property
    def ingest_engine(self) -> Any | None:
        return self._ctx.ingest_engine

    @property
    def retriever(self) -> Any | None:
        return self._ctx.retriever

    @property
    def generator(self) -> Any | None:
        return self._ctx.generator

    @property
    def chat_engine(self) -> Any | None:
        return self._ctx.chat_engine

    @property
    def manifest(self) -> Any | None:
        return self._ctx.manifest

    @property
    def config(self) -> Any:
        return self._ctx.config

    def save_config(self) -> None:
        """持久化当前配置。"""
        self._ctx.save_config()

    @property
    def root(self) -> Path:
        return self._ctx.root

    @property
    def embedding_model(self) -> Any | None:
        return self._ctx.embedding_model

    @property
    def sessions_path(self) -> Path:
        return self._ctx.sessions_path

    @property
    def co_dir(self) -> Path:
        return self._ctx.co_dir

    def save_config(self) -> None:
        """委托给 ProjectContext.save_config()。"""
        self._ctx.save_config()

    def scan_files(self, subdir: str | None = None) -> list[dict[str, Any]]:
        return self._ctx.scan_files(subdir=subdir)

    # ── 供 pytest fixture 使用的测试 hook ─────────────────────────

    @classmethod
    def _from_ctx(cls, ctx: Any) -> WorkspaceRuntime:
        """仅测试用——用已经组装好的 ProjectContext 构造 runtime。"""
        return cls(ctx)
