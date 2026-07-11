"""配置管理路由 — GET/POST /api/config"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.deps import get_project_context

import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["config"])

class ConfigUpdate(BaseModel):
    api_key: str | None = None
    base_url: str | None = None
    model: str | None = None
    top_k: int | None = None
    chunk_size: int | None = None


@router.get("/config")
async def get_config(
    ctx: Any = Depends(get_project_context),
):
    """返回当前配置（API key 仅返回是否存在）。"""
    return {
        "api_key_configured": bool(ctx.ctx.get_api_key()),
        "base_url": ctx.config.base_url,
        "model": ctx.config.model,
        "top_k": ctx.config.top_k,
        "chunk_size": ctx.config.chunk_size,
    }


@router.get("/models")
async def list_models(
    ctx: Any = Depends(get_project_context),
):
    """从当前配置的 API 提供商获取可用模型列表。"""
    api_key = ctx.ctx.get_api_key()
    if not api_key:
        return {"models": []}
    base_url = ctx.config.base_url
    fallback = [{"id": "deepseek-v4-flash", "name": "deepseek-v4-flash"}, {"id": "deepseek-v4-pro", "name": "deepseek-v4-pro"}]
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key, base_url=base_url)
        models = client.models.list()
        fetched = [{"id": m.id, "name": m.id} for m in sorted(models, key=lambda x: x.id)]
        return {"models": fetched if fetched else fallback}
    except Exception as e:
        logger.warning("Failed to fetch models from %s: %s", base_url, e)
        return {"models": fallback}


class TestConnectionRequest(BaseModel):
    api_key: str | None = None
    base_url: str | None = None
    model: str | None = None


@router.post("/config/test")
async def test_connection(
    req: TestConnectionRequest,
    ctx: Any = Depends(get_project_context),
):
    """测试 API 供应商连通性，返回延迟与状态。"""
    import time

    api_key = req.api_key or ctx.ctx.get_api_key()
    if not api_key:
        return {"status": "error", "model": req.model or ctx.config.model, "elapsed_ms": 0, "error": "未配置 API Key"}
    base_url = req.base_url or ctx.config.base_url
    model = req.model or ctx.config.model

    start = time.perf_counter()
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key, base_url=base_url)
        client.models.list()
        elapsed = round((time.perf_counter() - start) * 1000)
        return {"status": "ok", "model": model, "elapsed_ms": elapsed}
    except Exception as e:
        elapsed = round((time.perf_counter() - start) * 1000)
        # 过滤敏感信息，避免在 error 消息中泄露 API Key/URL
        err_msg = str(e)
        sanitized = err_msg
        if req.api_key:
            sanitized = sanitized.replace(req.api_key, "***")
            import urllib.parse
            encoded_key = urllib.parse.quote(req.api_key, safe="")
            if encoded_key != req.api_key:
                sanitized = sanitized.replace(encoded_key, "***")
        if req.base_url and req.base_url in sanitized:
            sanitized = sanitized.replace(req.base_url, "***")
        logger.warning("Connection test failed: %s", sanitized)
        return {"status": "error", "model": model, "elapsed_ms": elapsed, "error": sanitized}


@router.post("/config")
async def save_config(
    req: ConfigUpdate,
    ctx: Any = Depends(get_project_context),
):
    """保存配置更新到项目 config 和全局 config。"""
    if req.top_k is not None:
        ctx.config.top_k = req.top_k
    if req.chunk_size is not None:
        ctx.config.chunk_size = req.chunk_size
    if req.model is not None:
        ctx.config.model = req.model
    if req.base_url is not None:
        ctx.config.base_url = req.base_url

    ctx.save_config()

    if req.api_key is not None or req.base_url is not None:
        try:
            import tomli_w
            from core.project import GLOBAL_CONFIG_PATH, _load_global_config
            global_cfg = _load_global_config()
            if req.api_key is not None:
                global_cfg.setdefault("auth", {})
                global_cfg["auth"]["api_key"] = req.api_key
                os.environ["DEEPSEEK_API_KEY"] = req.api_key
            if req.base_url is not None:
                global_cfg.setdefault("model", {})
                global_cfg["model"]["base_url"] = req.base_url
            GLOBAL_CONFIG_PATH.write_text(tomli_w.dumps(global_cfg), encoding="utf-8")

            ctx.ctx._global_config = global_cfg

            try:
                ctx.ctx.llm = ctx.ctx.get_llm()
            except Exception:
                ctx.ctx.llm = None
            ctx.ctx.embedding_model = ctx.ctx.get_embedding_model()
            ctx.ctx.setup_engines()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"保存 API 配置失败: {e}")

    return {"status": "ok"}
