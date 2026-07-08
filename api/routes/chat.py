"""WebSocket 流式问答路由 — WS /api/ws/chat"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from typing import Any

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from api.deps import get_project_context

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])


@router.websocket("/ws/chat")
async def chat_websocket(
    ws: WebSocket,
    ctx: Any = Depends(get_project_context),
):
    """
    WebSocket 流式问答。

    协议（JSON 消息）：
    接收: {"type": "query", "content": "...", "session_id": "..."}
    发送: {"type": "chunk", "content": "..."}
    发送: {"type": "done", "session_id": "...", "references": [...]}
    发送: {"type": "error", "message": "..."}
    """
    await ws.accept()

    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await ws.send_json({"type": "error", "message": "Invalid JSON"})
                continue

            if msg.get("type") != "query":
                await ws.send_json({"type": "error", "message": "Expected type 'query'"})
                continue

            query_text = msg.get("content", "").strip()
            if not query_text:
                await ws.send_json({"type": "error", "message": "Empty query"})
                continue

            session_id = msg.get("session_id", None)

            if not ctx.llm:
                await ws.send_json({"type": "error", "message": "API Key 未配置，请在 .co-thinker/.env 中设置 DEEPSEEK_API_KEY"})
                continue

            # 确保有索引数据
            if not ctx.vectorstore or ctx.vectorstore.count_chunks() == 0:
                await ws.send_json({"type": "error", "message": "知识库为空，请先在文件管理页索引文档"})
                continue

            try:
                await _handle_query(ws, ctx, query_text, session_id)
            except Exception as exc:
                logger.exception("Chat error")
                await ws.send_json({"type": "error", "message": str(exc)})

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")


async def _handle_query(
    ws: WebSocket,
    ctx: Any,
    query_text: str,
    session_id: str | None,
) -> None:
    """处理单个查询：检索 → 生成 → 流式推送。"""
    # 获取会话历史
    history = None
    if session_id and ctx.chat_engine:
        conversation = ctx.chat_engine.conversations.get(session_id)
        if conversation:
            history = conversation.to_llm_history(ctx.config.max_history_turns)
            ctx.chat_engine.current_id = session_id

    # 检索
    retrieval_results = ctx.retriever.retrieve(
        query=query_text,
        chat_history=history,
    )

    # 发送检索详情
    retrieval_details = None
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
                    "vector_score": round(r.vector_score, 4) if r.vector_score is not None else None,
                    "bm25_score": round(r.bm25_score, 4) if r.bm25_score is not None else None,
                }
                for r in retrieval_results.results[:5]
            ],
        }
        await ws.send_json({"type": "retrieval_done", **retrieval_details})

    if not retrieval_results.results:
        if ctx.chat_engine:
            ctx.chat_engine.add_user_message(query_text)
            ctx.chat_engine.add_assistant_message("知识库中未找到相关信息")
        await ws.send_json({
            "type": "done",
            "session_id": ctx.chat_engine.current_id if ctx.chat_engine else None,
            "references": [],
            "confidence": "none",
        })
        return

    # 记录用户消息
    if ctx.chat_engine:
        ctx.chat_engine.add_user_message(query_text, mode="rag")

    # 流式生成
    full_answer = ""
    reasoning_text = ""
    async for event_type, content in _stream_generate(ctx, query_text, retrieval_results, history):
        if event_type == "reasoning":
            reasoning_text += content
            await ws.send_json({"type": "reasoning", "content": content})
        else:
            full_answer += content
            await ws.send_json({"type": "chunk", "content": content})

    # 记录助手消息（附加检索与推理元数据）
    metadata = {}
    if retrieval_details:
        metadata["retrieval_details"] = retrieval_details
    if reasoning_text:
        metadata["reasoning_text"] = reasoning_text
    if ctx.chat_engine:
        ctx.chat_engine.add_assistant_message(full_answer, **metadata)

    # 发送完成信号
    references = retrieval_results.to_sources()[:10]
    await ws.send_json({
        "type": "done",
        "session_id": ctx.chat_engine.current_id if ctx.chat_engine else None,
        "references": references,
        "confidence": retrieval_results.confidence,
    })


async def _stream_generate(
    ctx: Any,
    query_text: str,
    retrieval_results: Any,
    history: list[dict[str, str]] | None,
):
    """流式生成回答 — 使用 asyncio.Queue 桥接同步生成器到异步上下文，实现逐块推送。"""
    loop = asyncio.get_event_loop()
    queue: asyncio.Queue = asyncio.Queue(maxsize=64)

    def _produce():
        try:
            for event in ctx.generator.stream_generate(query_text, retrieval_results, history):
                future = asyncio.run_coroutine_threadsafe(queue.put(event), loop)
                future.result()
        except Exception as exc:
            logger.exception("Generation error in thread")
            future = asyncio.run_coroutine_threadsafe(
                queue.put(("content", f"生成答案时发生错误：{str(exc)}")),
                loop,
            )
            future.result()
        finally:
            asyncio.run_coroutine_threadsafe(queue.put(None), loop).result()

    thread = threading.Thread(target=_produce, daemon=True)
    thread.start()

    while True:
        event = await queue.get()
        if event is None:
            break
        yield event
