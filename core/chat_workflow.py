"""
ChatWorkflow — 纯 RAG 对话流程实现。

职责：
  1. 接收用户查询和会话 ID
  2. 读取历史 → 检索 → 流式生成 → 持久化消息
  3. 向外发射类型化事件（retrieval_done / chunk / reasoning / done / error）

与 FastAPI / WebSocket 零耦合，可在纯函数测试中验证。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Generator

logger = logging.getLogger(__name__)


@dataclass
class WorkflowEvent:
    """工作流事件——route adapter 将其转换为 HTTP/WS 格式。"""
    type: str  # "retrieval_done" | "chunk" | "reasoning" | "done" | "error"
    data: dict[str, Any] = field(default_factory=dict)


class ChatWorkflow:
    """RAG 对话流程——纯业务逻辑，不依赖 FastAPI / WebSocket。"""

    def __init__(self, runtime: Any):
        self._runtime = runtime

    @property
    def _ctx(self) -> Any:
        return self._runtime.ctx

    def execute(
        self,
        query: str,
        session_id: str | None = None,
    ) -> Generator[WorkflowEvent, None, None]:
        """执行一轮 RAG 问答，返回事件序列。

        事件顺序（正常路径）：
          retrieval_done → (reasoning*) → (chunk*) → done

        事件顺序（空结果）：
          done (zero references)

        事件顺序（异常）：
          error
        """
        ctx = self._ctx

        # ── 1. 获取会话历史 ──────────────────────────────────────────
        history = None
        if session_id and ctx.chat_engine:
            conversation = ctx.chat_engine.conversations.get(session_id)
            if conversation:
                history = conversation.to_llm_history(ctx.config.max_history_turns)
                ctx.chat_engine.current_id = session_id

        # ── 2. 检索 ──────────────────────────────────────────────────
        try:
            retrieval_results = ctx.retriever.retrieve(
                query=query,
                chat_history=history,
            )
        except Exception as exc:
            logger.exception("Retrieval failed")
            yield WorkflowEvent("error", {"message": f"检索失败：{exc}"})
            return

        # ── 3. 构造检索详情事件 ──────────────────────────────────────
        retrieval_details: dict[str, Any] | None = None
        if retrieval_results.results:
            retrieval_details = {
                "mode": retrieval_results.mode,
                "elapsed_ms": round(retrieval_results.elapsed_ms, 1),
                "total_candidates": retrieval_results.total_candidates,
                "effective_query": retrieval_results.effective_query,
                "results": [
                    {
                        "chunk_id": r.chunk_id,
                        "source_path": r.source_path,
                        "file_name": r.file_name,
                        "score": round(r.final_score, 4),
                        "matched_by": r.matched_by,
                        "vector_score": round(r.vector_score, 4)
                        if r.vector_score is not None else None,
                        "bm25_score": round(r.bm25_score, 4)
                        if r.bm25_score is not None else None,
                    }
                    for r in retrieval_results.results[:5]
                ],
            }
            yield WorkflowEvent("retrieval_done", retrieval_details)

        # ── 4. 无检索结果 ────────────────────────────────────────────
        if not retrieval_results.results:
            if ctx.chat_engine:
                ctx.chat_engine.add_user_message(query)
                ctx.chat_engine.add_assistant_message("知识库中未找到相关信息")
            yield WorkflowEvent("done", {
                "session_id": ctx.chat_engine.current_id if ctx.chat_engine else None,
                "references": [],
                "confidence": "none",
            })
            return

        # ── 5. 记录用户消息 ──────────────────────────────────────────
        if ctx.chat_engine:
            ctx.chat_engine.add_user_message(query, mode="rag")

        # ── 6. 流式生成 ──────────────────────────────────────────────
        full_answer = ""
        reasoning_text = ""
        for event_type, content in ctx.generator.stream_generate(
            query, retrieval_results, history
        ):
            if event_type == "reasoning":
                reasoning_text += content
                yield WorkflowEvent("reasoning", {"content": content})
            else:
                full_answer += content
                yield WorkflowEvent("chunk", {"content": content})

        # ── 7. 持久化助手消息 ────────────────────────────────────────
        metadata: dict[str, Any] = {}
        if retrieval_details:
            metadata["retrieval_details"] = retrieval_details
        if reasoning_text:
            metadata["reasoning_text"] = reasoning_text
        if ctx.chat_engine:
            ctx.chat_engine.add_assistant_message(full_answer, **metadata)

        # ── 8. 完成 ──────────────────────────────────────────────────
        references = retrieval_results.to_sources()[:10]
        yield WorkflowEvent("done", {
            "session_id": ctx.chat_engine.current_id if ctx.chat_engine else None,
            "references": references,
            "confidence": retrieval_results.confidence,
        })
