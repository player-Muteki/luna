"""
API 依赖注入 — 提供 WorkspaceRuntime 给各路由。

现在由 ``core.runtime.WorkspaceRuntime.bootstrap()`` 统一处理
工作目录加载、模型初始化、引擎组装。路由通过 WorkspaceRuntime
的委托属性访问内部引擎（Phase 5 再逐步深化）。
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_project_context(explicit: str | None = None) -> Any:
    """延迟创建并缓存 WorkspaceRuntime（进程生命周期内只创建一次）。

    返回 ``WorkspaceRuntime`` 实例，路由通过其委托属性
    访问 LLM / 引擎 / 配置。
    """
    from core.runtime import WorkspaceRuntime

    runtime = WorkspaceRuntime.bootstrap(explicit)
    logger.info("WorkspaceRuntime loaded: %s", runtime.root)
    return runtime
