"""索引管理路由 — POST /api/ingest, DELETE /api/ingest"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.deps import get_project_context

router = APIRouter(tags=["ingest"])


class IngestRequest(BaseModel):
    paths: list[str]


@router.post("/ingest")
async def ingest_files(
    req: IngestRequest,
    ctx: Any = Depends(get_project_context),
):
    """索引指定文件。"""
    if not ctx.ingest_engine:
        raise HTTPException(status_code=500, detail="Ingest engine not initialized")

    # 将相对路径解析为绝对路径
    file_paths = [str(ctx.root / p) if not Path(p).is_absolute() else p for p in req.paths]

    summary = ctx.ingest_engine.add_files(file_paths)
    # 通知检索器重建 IDF 缓存
    if ctx.retriever:
        ctx.retriever.invalidate_idf_cache()

    return {
        "total_files": summary.total_files,
        "indexed_files": summary.indexed_files,
        "skipped_files": summary.skipped_files,
        "failed_files": summary.failed_files,
        "total_chunks": summary.total_chunks,
        "elapsed_ms": summary.elapsed_ms,
        "results": [
            {"path": r.path, "status": r.status, "document_id": r.document_id, "chunk_count": r.chunk_count, "error": r.error}
            for r in summary.results
        ],
    }


@router.post("/ingest/scan")
async def scan_and_index(
    ctx: Any = Depends(get_project_context),
):
    """扫描工作目录并增量重建索引。"""
    if not ctx.ingest_engine:
        raise HTTPException(status_code=500, detail="Ingest engine not initialized")

    summary = ctx.ingest_engine.rebuild_index(force=False)
    if ctx.retriever:
        ctx.retriever.invalidate_idf_cache()

    return {
        "total_files": summary.total_files,
        "indexed_files": summary.indexed_files,
        "skipped_files": summary.skipped_files,
        "failed_files": summary.failed_files,
        "total_chunks": summary.total_chunks,
        "elapsed_ms": summary.elapsed_ms,
    }


@router.post("/ingest/rebuild")
async def rebuild_index(
    ctx: Any = Depends(get_project_context),
):
    """强制全量重建索引。"""
    if not ctx.ingest_engine:
        raise HTTPException(status_code=500, detail="Ingest engine not initialized")

    summary = ctx.ingest_engine.rebuild_index(force=True)
    if ctx.retriever:
        ctx.retriever.invalidate_idf_cache()

    return {
        "total_files": summary.total_files,
        "indexed_files": summary.indexed_files,
        "skipped_files": summary.skipped_files,
        "failed_files": summary.failed_files,
        "total_chunks": summary.total_chunks,
        "elapsed_ms": summary.elapsed_ms,
    }


@router.delete("/ingest/{document_id:str}")
async def delete_document(
    document_id: str,
    ctx: Any = Depends(get_project_context),
):
    """删除指定文档的索引。"""
    if not ctx.ingest_engine:
        raise HTTPException(status_code=500, detail="Ingest engine not initialized")

    try:
        result = ctx.ingest_engine.delete_file(document_id)
        if ctx.retriever:
            ctx.retriever.invalidate_idf_cache()
        return {"status": "deleted", "path": result.path, "chunk_count": result.chunk_count}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
