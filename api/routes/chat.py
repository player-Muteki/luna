"""WebSocket 流式问答路由 — WS /api/ws/chat

Route adapter — 只负责 WebSocket 协议转换，业务流程委托给 ``ChatWorkflow``。
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from typing import Any

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from api.deps import get_project_context
from core.chat_workflow import ChatWorkflow, WorkflowEvent

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])


@router.websocket("/ws/chat")
async def chat_websocket(
    ws: WebSocket,
    runtime: Any = Depends(get_project_context),
):
    """
    WebSocket 流式问答。

    Route adapter — 所有业务逻辑委托给 ``ChatWorkflow``。
    """
    await ws.accept()

    # ── 前置检查 ─────────────────────────────────────────────────
    if not runtime.llm:
        await ws.send_json({"type": "error", "message": "API Key 未配置，请在 .lore/.env 中设置 DEEPSEEK_API_KEY"})
        await ws.close()
        return

    if not runtime.vectorstore or runtime.vectorstore.count_chunks() == 0:
        await ws.send_json({"type": "error", "message": "知识库为空，请先在文件管理页索引文档"})
        await ws.close()
        return

    # ── 消息循环 ─────────────────────────────────────────────────
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
            request_model = msg.get("model", None)

            try:
                workflow = ChatWorkflow(runtime)
                async for event in _run_workflow(workflow, query_text, session_id, request_model):
                    await ws.send_json(_event_to_ws(event))
            except Exception as exc:
                logger.exception("Chat error")
                await ws.send_json({"type": "error", "message": str(exc)})
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")


# ── 同步 → 异步桥接 ───────────────────────────────────────────


async def _run_workflow(
    workflow: ChatWorkflow,
    query: str,
    session_id: str | None,
    model: str | None = None,
) -> Any:
    """在后台线程中运行 sync workflow.execute()，通过 asyncio.Queue 推送事件。"""
    loop = asyncio.get_event_loop()
    queue: asyncio.Queue = asyncio.Queue(maxsize=64)

    def _produce() -> None:
        try:
            for event in workflow.execute(query, session_id, model=model):
                future = asyncio.run_coroutine_threadsafe(queue.put(event), loop)
                future.result()
        except Exception as exc:
            logger.exception("Workflow thread error")
            future = asyncio.run_coroutine_threadsafe(
                queue.put(WorkflowEvent("error", {"message": str(exc)})),
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


def _event_to_ws(event: WorkflowEvent) -> dict[str, Any]:
    """将 WorkflowEvent 转换为 WebSocket JSON payload。"""
    if event.type == "error":
        return {"type": "error", "message": event.data.get("message", "")}
    return {"type": event.type, **event.data}
