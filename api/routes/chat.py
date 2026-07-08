"""WebSocket 流式问答路由 — WS /api/ws/chat"""

from __future__ import annotations

import json
import logging
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

    if not retrieval_results.results:
        # 记录用户消息 + 空回答
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
    async for chunk_text in _stream_generate(ctx, query_text, retrieval_results, history):
        full_answer += chunk_text
        await ws.send_json({"type": "chunk", "content": chunk_text})
        import asyncio
        await asyncio.sleep(0)  # yield to event loop

    # 记录助手消息
    if ctx.chat_engine:
        ctx.chat_engine.add_assistant_message(full_answer)

    # 发送完成信号
    references = retrieval_results.to_sources()[:10] if retrieval_results.results else []
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
    """流式生成回答的异步包装。"""
    loop = None
    try:
        import asyncio
        loop = asyncio.get_event_loop()

        def _sync_stream():
            return list(ctx.generator.stream_generate(query_text, retrieval_results, history))

        chunks = await loop.run_in_executor(None, _sync_stream)
        for chunk in chunks:
            yield chunk
    except Exception as exc:
        logger.exception("Generation error")
        yield f"生成答案时发生错误：{str(exc)}"
