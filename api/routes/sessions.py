"""会话管理路由 — CRUD for conversations."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.deps import get_project_context

router = APIRouter(tags=["sessions"])


class CreateSessionRequest(BaseModel):
    title: str = "新对话"


class RenameSessionRequest(BaseModel):
    title: str


@router.get("/sessions")
async def list_sessions(
    ctx: Any = Depends(get_project_context),
):
    """返回会话列表。"""
    if not ctx.chat_engine:
        return {"sessions": []}
    return {"sessions": ctx.chat_engine.list_conversations()}


@router.post("/sessions")
async def create_session(
    req: CreateSessionRequest,
    ctx: Any = Depends(get_project_context),
):
    """创建新会话。"""
    if not ctx.chat_engine:
        raise HTTPException(status_code=500, detail="Chat engine not initialized")

    conversation = ctx.chat_engine.create_conversation(title=req.title)
    return {
        "id": conversation.conversation_id,
        "title": conversation.title,
        "created_at": conversation.created_at,
    }


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: str,
    ctx: Any = Depends(get_project_context),
):
    """获取会话详情（消息列表）。"""
    if not ctx.chat_engine:
        raise HTTPException(status_code=500, detail="Chat engine not initialized")

    conversation = ctx.chat_engine.conversations.get(session_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Session not found")

    return {
        "id": conversation.conversation_id,
        "title": conversation.title,
        "created_at": conversation.created_at,
        "updated_at": conversation.updated_at,
        "messages": [
            {
                "id": msg.message_id,
                "role": msg.role,
                "content": msg.content,
                "created_at": msg.created_at,
                "metadata": msg.metadata,
            }
            for msg in conversation.messages
        ],
    }


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    ctx: Any = Depends(get_project_context),
):
    """删除会话。"""
    if not ctx.chat_engine:
        raise HTTPException(status_code=500, detail="Chat engine not initialized")

    success = ctx.chat_engine.delete_conversation(session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "deleted"}


@router.patch("/sessions/{session_id}")
async def rename_session(
    session_id: str,
    req: RenameSessionRequest,
    ctx: Any = Depends(get_project_context),
):
    """重命名会话。"""
    if not ctx.chat_engine:
        raise HTTPException(status_code=500, detail="Chat engine not initialized")

    success = ctx.chat_engine.rename_conversation(session_id, req.title)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "renamed", "title": req.title}
