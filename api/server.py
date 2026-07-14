"""FastAPI 应用入口 — 注册路由与中间件。"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from __version__ import __version__

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """应用生命周期管理。"""
    logger.info("Starting Luna API...")
    from api.deps import get_project_context
    ctx = get_project_context()
    logger.info("Project root: %s", ctx.root)
    yield
    logger.info("Luna API shutting down.")


app = FastAPI(
    title="Luna API",
    description="工作目录绑定型 RAG 知识库系统 API",
    version=__version__,
    lifespan=lifespan,
)

# CORS — 从环境变量读取
_default_cors = "*"
_cors_origins = os.getenv("CORS_ORIGINS", _default_cors).split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _cors_origins if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
from api.routes import files, ingest, sessions, chat, config, agent

app.include_router(files.router, prefix="/api")
app.include_router(ingest.router, prefix="/api")
app.include_router(sessions.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(config.router, prefix="/api")
app.include_router(agent.router, prefix="/api")


@app.get("/")
async def root():
    return {
        "name": "Luna API",
        "version": __version__,
        "endpoints": {
            "GET /api/project": "项目信息",
            "GET /api/files": "文件列表",
            "POST /api/ingest": "索引文件",
            "DELETE /api/ingest/{doc_id}": "删除文档索引",
            "GET /api/sessions": "会话列表",
            "POST /api/sessions": "新建会话",
            "GET /api/sessions/{id}": "会话详情",
            "DELETE /api/sessions/{id}": "删除会话",
            "PATCH /api/sessions/{id}": "重命名会话",
            "GET /api/stats": "索引统计",
            "WS /api/ws/chat": "流式问答",
            "POST /api/agent/run": "运行 Agent（SSE 流式）",
            "GET /api/agent/approvals": "Agent 审批列表",
            "POST /api/agent/approve/{id}": "批准工具调用",
            "POST /api/agent/reject/{id}": "拒绝工具调用",
            "GET /api/agent/sessions": "Agent 会话列表",
            "GET /api/agent/sessions/{id}": "Agent 会话详情",
        },
    }
