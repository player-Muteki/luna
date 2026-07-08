"""
API 依赖注入 — 提供 ProjectContext 给各路由。
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_project_context(explicit: str | None = None) -> Any:
    """延迟创建并缓存 ProjectContext（进程生命周期内只创建一次）。"""
    from core.project import ProjectContext, get_api_key, get_llm, get_embedding_model

    ctx = ProjectContext.load(explicit)

    # 设置 LLM
    if get_api_key(ctx):
        try:
            ctx.llm = get_llm(ctx)
        except Exception:
            pass

    # 设置 embedding 模型
    ctx.embedding_model = get_embedding_model(ctx)

    # 组装所有引擎
    ctx.setup_engines()

    logger.info("ProjectContext loaded: %s", ctx.root)
    return ctx
