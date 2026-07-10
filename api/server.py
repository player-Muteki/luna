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
    logger.info("Starting Co-Thinker API...")
    from api.deps import get_project_context
    ctx = get_project_context()
    logger.info("Project root: %s", ctx.root)
    yield
    logger.info("Co-Thinker API shutting down.")


app = FastAPI(
    title="Co-Thinker API",
    description="工作目录绑定型 RAG 知识库系统 API",
    version=__version__,
    lifespan=lifespan,
)

# CORS — 从环境变量读取，默认为 Next.js 开发/生产服务器地址
_default_cors = "http://localhost:3000,http://127.0.0.1:3000,http://localhost:3001,http://127.0.0.1:3001"
_cors_origins = os.getenv("CORS_ORIGINS", _default_cors).split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _cors_origins if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
from api.routes import files, ingest, sessions, chat, config

app.include_router(files.router, prefix="/api")
app.include_router(ingest.router, prefix="/api")
app.include_router(sessions.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(config.router, prefix="/api")


@app.get("/")
async def root():
    return {
        "name": "Co-Thinker API",
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
        },
    }
