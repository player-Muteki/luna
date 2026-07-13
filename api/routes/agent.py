"""Agent API 路由 — SSE 流式执行与 REST 管理。

Route adapter — 只负责 HTTP/SSE 协议转换，业务流程委托给 ``AgentWorkflow``。
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from starlette.requests import Request

from api.deps import get_project_context
from core.agent_modes import AgentMode, ApprovalMode

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["agent"])


# ── SSE 流式执行 ──────────────────────────────────────────────


@router.post("/run")
async def agent_run(
    body: dict[str, Any],
    request: Request,
    runtime: Any = Depends(get_project_context),
):
    """运行知识库 Agent，通过 SSE 流式输出事件。"""
    goal = body.get("goal", "").strip()
    if not goal:
        raise HTTPException(status_code=400, detail="goal is required")

    mode_name = body.get("mode", "default")
    approval_mode_name = body.get("approval_mode", "ask")
    generate_response = body.get("generate_response", False)

    try:
        mode = AgentMode(mode_name)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid mode: {mode_name}")

    try:
        approval_mode = ApprovalMode(approval_mode_name)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid approval_mode: {approval_mode_name}")

    return StreamingResponse(
        _stream_agent_events(runtime, goal, mode, approval_mode, generate_response, request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


async def _stream_agent_events(
    runtime: Any,
    goal: str,
    mode: AgentMode,
    approval_mode: ApprovalMode,
    generate_response: bool,
    request: Request,
) -> Any:
    """在后台线程运行 sync workflow.execute()，通过 SSE 推送事件。"""
    loop = asyncio.get_event_loop()
    queue: asyncio.Queue = asyncio.Queue(maxsize=64)

    def _produce() -> None:
        try:
            workflow = runtime.get_agent_workflow()
            for event in workflow.execute(goal, mode=mode, approval_mode=approval_mode, generate_response=generate_response):
                _put_on_queue(loop, queue, event.to_dict())
        except Exception as exc:
            logger.exception("Agent workflow error")
            _put_on_queue(loop, queue, {"type": "error", "error": str(exc)})
        finally:
            _put_on_queue(loop, queue, None)

    thread = threading.Thread(target=_produce, daemon=True)
    thread.start()

    while True:
        if await request.is_disconnected():
            break
        try:
            event = await asyncio.wait_for(queue.get(), timeout=30.0)
        except asyncio.TimeoutError:
            yield f": keepalive\n\n"
            continue
        if event is None:
            break
        yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


# ── 审批管理 ──────────────────────────────────────────────────


@router.get("/approvals")
async def list_approvals(
    runtime: Any = Depends(get_project_context),
):
    """列出所有 Agent 工具审批。"""
    workflow = runtime.get_agent_workflow()
    return {"approvals": [a.to_dict() for a in workflow.list_approvals()]}


@router.post("/approve/{approval_id}")
async def approve_tool(
    approval_id: str,
    runtime: Any = Depends(get_project_context),
):
    """批准并执行一个 Agent 工具调用。"""
    workflow = runtime.get_agent_workflow()
    approval = workflow.approve(approval_id)
    payload = {"approval": approval.to_dict()}

    execution_events = list(workflow.execute_approved(approval_id))
    payload["events"] = [e.to_dict() for e in execution_events]

    return payload


@router.post("/reject/{approval_id}")
async def reject_tool(
    approval_id: str,
    runtime: Any = Depends(get_project_context),
):
    """拒绝一个 Agent 工具调用。"""
    workflow = runtime.get_agent_workflow()
    approval = workflow.reject(approval_id)
    return {"approval": approval.to_dict()}


# ── 会话管理 ──────────────────────────────────────────────────


@router.get("/sessions")
async def list_sessions(
    runtime: Any = Depends(get_project_context),
):
    """列出所有 Agent 会话。"""
    workflow = runtime.get_agent_workflow()
    return {"sessions": [s.to_dict() for s in workflow.list_sessions()]}


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: str,
    runtime: Any = Depends(get_project_context),
):
    """获取 Agent 会话事件列表。"""
    workflow = runtime.get_agent_workflow()
    events = workflow.read_session(session_id)
    if not events:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"events": events}


# ── 内部助手 ──────────────────────────────────────────────────


def _put_on_queue(loop: asyncio.AbstractEventLoop, queue: asyncio.Queue, item: Any) -> None:
    future = asyncio.run_coroutine_threadsafe(queue.put(item), loop)
    future.result()
