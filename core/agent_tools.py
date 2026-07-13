from __future__ import annotations

from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from core.runtime import WorkspaceRuntime


class KnowledgeToolset:
    """WorkspaceRuntime 的知识库工具适配层。"""

    def __init__(self, runtime: "WorkspaceRuntime"):
        self._runtime = runtime

    def tool_names(self) -> list[str]:
        return list(self._handlers())

    def call(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        handlers = self._handlers()
        try:
            handler = handlers[name]
        except KeyError as exc:
            raise ValueError(f"Unknown knowledge tool: {name}") from exc
        return handler(arguments or {})

    def _handlers(self) -> dict[str, Any]:
        return {
            "kb_get_stats": self._kb_get_stats,
            "kb_list_files": self._kb_list_files,
            "kb_list_documents": self._kb_list_documents,
            "kb_search": self._kb_search,
            "kb_index_files": self._kb_index_files,
            "kb_rebuild_index": self._kb_rebuild_index,
            "kb_delete_document": self._kb_delete_document,
            "kb_update_tags": self._kb_update_tags,
            "kb_clear_index": self._kb_clear_index,
        }

    def _kb_get_stats(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return self._runtime.get_stats()

    def _kb_list_files(self, arguments: dict[str, Any]) -> dict[str, Any]:
        subdir = self._optional_str(arguments, "subdir")
        search = self._optional_str(arguments, "search")
        items = self._runtime.scan_files(subdir=subdir)

        if search:
            needle = search.casefold()
            items = [
                item for item in items
                if needle in item["path"].casefold() or needle in item["name"].casefold()
            ]

        return {
            "subdir": subdir,
            "search": search,
            "count": len(items),
            "items": items,
        }

    def _kb_list_documents(self, arguments: dict[str, Any]) -> dict[str, Any]:
        status = self._optional_str(arguments, "status") or "all"
        if status not in {"all", "indexed", "failed"}:
            raise ValueError("status must be one of: all, indexed, failed")

        documents = self._require_ingest_engine().list_documents()
        if status != "all":
            documents = [doc for doc in documents if doc.get("status") == status]

        return {
            "status": status,
            "count": len(documents),
            "documents": documents,
        }

    def _kb_search(self, arguments: dict[str, Any]) -> dict[str, Any]:
        query = self._required_str(arguments, "query")
        top_k = self._optional_int(arguments, "top_k") or 5
        results = self._require_retriever().retrieve(query=query, top_k=top_k)

        return {
            "query": results.original_query,
            "effective_query": results.effective_query,
            "mode": results.mode,
            "total_candidates": results.total_candidates,
            "elapsed_ms": round(results.elapsed_ms, 1),
            "count": len(results.results),
            "results": [
                {
                    "chunk_id": item.chunk_id,
                    "document_id": item.document_id,
                    "source_path": item.source_path,
                    "file_name": item.file_name,
                    "score": item.final_score,
                    "matched_by": item.matched_by,
                    "text": item.text,
                }
                for item in results.results
            ],
        }

    def _kb_index_files(self, arguments: dict[str, Any]) -> dict[str, Any]:
        raw_paths = arguments.get("paths")
        if not isinstance(raw_paths, list) or not raw_paths:
            raise ValueError("paths must be a non-empty list")
        paths = self._resolve_workspace_paths(raw_paths)
        summary = self._require_ingest_engine().add_files(paths)
        self._invalidate_retriever_cache()
        return self._serialize(summary)

    def _kb_rebuild_index(self, arguments: dict[str, Any]) -> dict[str, Any]:
        force = bool(arguments.get("force", False))
        engine = self._require_ingest_engine()
        summary = engine.force_rebuild_index() if force else engine.rebuild_index()
        self._invalidate_retriever_cache()
        return self._serialize(summary)

    def _kb_delete_document(self, arguments: dict[str, Any]) -> dict[str, Any]:
        document_id = self._required_str(arguments, "document_id")
        result = self._require_ingest_engine().delete_file(document_id)
        self._invalidate_retriever_cache()
        return self._serialize(result)

    def _kb_update_tags(self, arguments: dict[str, Any]) -> dict[str, Any]:
        document_id = self._required_str(arguments, "document_id")
        tags = arguments.get("tags")
        if not isinstance(tags, list):
            raise ValueError("tags must be a list")

        record = self._require_ingest_engine().update_document_tags(document_id, tags)
        if record is None:
            raise ValueError(f"Document not found: {document_id}")

        self._update_chunk_tags(document_id, tags)
        self._invalidate_retriever_cache()
        return record

    def _kb_clear_index(self, arguments: dict[str, Any]) -> dict[str, Any]:
        self._require_ingest_engine().clear_index()
        self._invalidate_retriever_cache()
        return {"cleared": True}

    def _require_ingest_engine(self) -> Any:
        engine = self._runtime.ingest_engine
        if engine is None:
            raise RuntimeError("Ingestion engine is not available")
        return engine

    def _require_retriever(self) -> Any:
        retriever = self._runtime.retriever
        if retriever is None:
            raise RuntimeError("Retriever is not available")
        return retriever

    def _resolve_workspace_paths(self, raw_paths: list[Any]) -> list[Path]:
        root = self._runtime.root.resolve()
        resolved_paths: list[Path] = []
        for raw_path in raw_paths:
            if not isinstance(raw_path, str) or not raw_path.strip():
                raise ValueError("paths must contain non-empty strings")
            candidate = (root / raw_path).resolve() if not Path(raw_path).is_absolute() else Path(raw_path).resolve()
            try:
                candidate.relative_to(root)
            except ValueError as exc:
                raise ValueError(f"Path escapes workspace: {raw_path}") from exc
            resolved_paths.append(candidate)
        return resolved_paths

    def _update_chunk_tags(self, document_id: str, tags: list[str]) -> None:
        vectorstore = self._runtime.vectorstore
        if vectorstore is None or not hasattr(vectorstore, "records"):
            return
        changed = False
        for record in vectorstore.records.values():
            if record.get("document_id") != document_id:
                continue
            metadata = record.setdefault("metadata", {})
            if metadata.get("tags") == tags:
                continue
            metadata["tags"] = tags
            changed = True
        if changed and hasattr(vectorstore, "flush"):
            vectorstore.flush()

    def _invalidate_retriever_cache(self) -> None:
        retriever = self._runtime.retriever
        if retriever is None:
            return
        if hasattr(retriever, "_idf_cache"):
            retriever._idf_cache = None
        if hasattr(retriever, "_idf_avgdl"):
            retriever._idf_avgdl = 0.0
        if hasattr(retriever, "_idf_n"):
            retriever._idf_n = 0

    @staticmethod
    def _serialize(value: Any) -> dict[str, Any]:
        if is_dataclass(value):
            return asdict(value)
        if isinstance(value, dict):
            return value
        raise TypeError(f"Unsupported tool result type: {type(value)!r}")

    @staticmethod
    def _required_str(arguments: dict[str, Any], key: str) -> str:
        value = arguments.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{key} must be a non-empty string")
        return value

    @staticmethod
    def _optional_str(arguments: dict[str, Any], key: str) -> str | None:
        value = arguments.get(key)
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError(f"{key} must be a string")
        value = value.strip()
        return value or None

    @staticmethod
    def _optional_int(arguments: dict[str, Any], key: str) -> int | None:
        value = arguments.get(key)
        if value is None:
            return None
        if not isinstance(value, int):
            raise ValueError(f"{key} must be an integer")
        return value
