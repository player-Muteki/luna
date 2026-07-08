"""
API 依赖注入 — 提供 ProjectContext 给各路由。
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_project_context(explicit: str | None = None) -> Any:
    """延迟创建并缓存 ProjectContext（进程生命周期内只创建一次）。"""
    from core.project import ProjectContext
    from core.ingest import IngestionEngine, JsonVectorStore, DocumentManifest
    from core.retriever import HybridRetriever
    from core.generator import RAGGenerator
    from core.chat_engine import ChatEngine

    ctx = ProjectContext.load(explicit)
    ctx._ensure_co_dir()

    # 加载或创建 API Key
    api_key = _get_api_key(ctx)
    llm = None
    if api_key:
        try:
            from core.project import get_llm
            llm = get_llm(ctx)
            ctx.llm = llm
        except Exception:
            pass

    embedding_model = _get_embedding(ctx)
    ctx.embedding_model = embedding_model

    vectorstore = JsonVectorStore(ctx.chunks_path)
    ctx.vectorstore = vectorstore

    manifest = DocumentManifest(ctx.manifest_path)
    ctx.manifest = manifest

    ingest = IngestionEngine(
        config=ctx.config,
        root=ctx.root,
        embedding_model=embedding_model,
        vector_store=vectorstore,
    )
    ctx.ingest_engine = ingest

    retriever = HybridRetriever(
        config=ctx.config,
        vector_store=vectorstore,
        embedding_model=embedding_model,
    )
    ctx.retriever = retriever

    chat_engine = ChatEngine(
        storage_path=ctx.sessions_path,
        max_history_turns=ctx.config.max_history_turns,
    )
    ctx.chat_engine = chat_engine

    generator = RAGGenerator(config=ctx.config, llm=llm)
    ctx.generator = generator

    logger.info("ProjectContext loaded: %s (chunks=%d)", ctx.root, vectorstore.count_chunks())
    return ctx


def _get_api_key(ctx: Any) -> str:
    """读取 API Key."""
    import os, re
    key = os.getenv("DEEPSEEK_API_KEY", "")
    if not key and ctx.env_path.exists():
        m = re.search(r'^DEEPSEEK_API_KEY=(.+)$', ctx.env_path.read_text(encoding="utf-8"), re.MULTILINE)
        if m:
            key = m.group(1).strip().strip('"\'')
    return key


def _get_embedding(ctx: Any) -> Any | None:
    """创建 embedding 模型（如果配置了）。"""
    if not ctx.config.embedding_model:
        return None
    try:
        from openai import OpenAI
    except ImportError:
        return None
    api_key = ctx.config.embedding_api_key or _get_api_key(ctx)
    client = OpenAI(api_key=api_key or "not-needed", base_url=ctx.config.embedding_base_url)

    class EmbeddingModel:
        def __init__(self, model_name: str, client: Any):
            self.model_name = model_name
            self.client = client
        def get_text_embedding(self, text: str) -> list[float]:
            return self.get_text_embedding_batch([text])[0]
        def get_query_embedding(self, query: str) -> list[float]:
            return self.get_text_embedding(query)
        def get_text_embedding_batch(self, texts: list[str]) -> list[list[float]]:
            response = self.client.embeddings.create(input=texts, model=self.model_name)
            return [item.embedding for item in response.data]

    return EmbeddingModel(ctx.config.embedding_model, client)
