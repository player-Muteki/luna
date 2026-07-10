from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

from core.parser import DocumentParser, PARSER_REGISTRY
from core.project import ProjectConfig


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_text(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n").strip()


def sha256_bytes(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def build_document_id(source_path: str) -> str:
    digest = hashlib.sha1(source_path.encode("utf-8")).hexdigest()[:12]
    return f"doc_{digest}"


@dataclass
class ChunkRecord:
    chunk_id: str
    document_id: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)
    embedding: list[float] | None = None


@dataclass
class FileIngestResult:
    path: str
    status: str
    document_id: str
    chunk_count: int = 0
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class IngestSummary:
    total_files: int
    indexed_files: int
    skipped_files: int
    failed_files: int
    total_chunks: int
    elapsed_ms: float
    results: list[FileIngestResult] = field(default_factory=list)


class DocumentManifest:
    def __init__(self, path: Path):
        self.path = path
        self.data = {"version": 1, "documents": {}}
        self.load()

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            self.data = {"version": 1, "documents": {}}
            return self.data
        self.data = json.loads(self.path.read_text(encoding="utf-8"))
        self.data.setdefault("version", 1)
        self.data.setdefault("documents", {})
        return self.data

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self.data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def clear(self) -> None:
        self.data = {"version": 1, "documents": {}}
        self.save()

    def upsert_document(self, record: dict[str, Any]) -> None:
        self.data["documents"][record["document_id"]] = record
        self.save()

    def mark_failed(self, source_path: str, error: str, document_id: str | None = None) -> None:
        existing = self.find_by_path(source_path)
        doc_id = document_id or build_document_id(source_path)
        now = utc_now_iso()
        record = {
            "document_id": doc_id,
            "source_path": source_path,
            "file_name": Path(source_path).name,
            "file_ext": Path(source_path).suffix.lower(),
            "content_hash": (existing or {}).get("content_hash", ""),
            "mtime": (existing or {}).get("mtime", 0.0),
            "size_bytes": (existing or {}).get("size_bytes", 0),
            "chunk_count": 0,
            "tags": (existing or {}).get("tags", []),
            "status": "failed",
            "created_at": (existing or {}).get("created_at", now),
            "updated_at": now,
            "last_error": error,
        }
        self.upsert_document(record)

    def remove_document(self, document_id: str) -> None:
        self.data["documents"].pop(document_id, None)
        self.save()

    def find_by_path(self, source_path: str) -> dict[str, Any] | None:
        for record in self.data["documents"].values():
            if record.get("source_path") == source_path:
                return record
        return None

    def get(self, document_id: str) -> dict[str, Any] | None:
        return self.data["documents"].get(document_id)

    def list_documents(self) -> list[dict[str, Any]]:
        return list(self.data["documents"].values())

    def update_tags(self, document_id: str, tags: list[str]) -> dict[str, Any] | None:
        """更新指定文档的 tags 字段并持久化。"""
        doc = self.data["documents"].get(document_id)
        if not doc:
            return None
        doc["tags"] = tags
        doc["updated_at"] = utc_now_iso()
        self.save()
        return doc


class VectorStore:
    def __init__(self, path: Path):
        self.path = path
        self.records: dict[str, dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            self.records = {}
            return
        self.records = json.loads(self.path.read_text(encoding="utf-8"))

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self.records, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def upsert_chunks(self, chunks: list[ChunkRecord]) -> None:
        """Insert or update chunks in memory.  Caller must call ``flush()`` to persist."""
        for chunk in chunks:
            self.records[chunk.chunk_id] = asdict(chunk)

    def flush(self) -> None:
        """Flush in-memory records to disk."""
        self._save()

    def delete_by_document_id(self, document_id: str) -> int:
        removed_ids = [
            chunk_id
            for chunk_id, record in self.records.items()
            if record.get("document_id") == document_id
        ]
        for chunk_id in removed_ids:
            self.records.pop(chunk_id, None)
        if removed_ids:
            self._save()
        return len(removed_ids)

    def clear(self) -> None:
        self.records = {}
        self._save()

    def count_chunks(self) -> int:
        return len(self.records)

    def count_documents(self) -> int:
        return len({record["document_id"] for record in self.records.values()})

    def iter_records(self) -> list[dict[str, Any]]:
        return list(self.records.values())

    def get_record(self, chunk_id: str) -> dict[str, Any] | None:
        return self.records.get(chunk_id)


class IngestionEngine:
    def __init__(self, config: ProjectConfig, root: Path | None = None, embedding_model: Any | None = None, vector_store: Any | None = None, parser_registry: dict[str, DocumentParser] | None = None):
        self.config = config
        self.root = (root or Path.cwd()).resolve()
        self.embedding_model = embedding_model
        self.co_dir = self.root / ".co-thinker"
        self.vector_store = vector_store or VectorStore(self.co_dir / "vectordb" / "chunks.json")
        self.manifest = DocumentManifest(self.co_dir / "vectordb" / "manifest.json")
        self.parser_registry = parser_registry if parser_registry is not None else PARSER_REGISTRY

    def scan_files(self, root_dir: str | Path | None = None) -> list[Path]:
        """扫描工作目录，返回可索引文件路径。

        由 ``FileCatalog.ingest_candidates()`` 实现。
        """
        from core.file_catalog import FileCatalog

        catalog = FileCatalog(
            root=self.root,
            exclude_patterns=self.config.exclude_patterns,
            supported_extensions=self.config.supported_extensions,
            max_file_size_mb=self.config.max_file_size_mb,
        )
        return catalog.ingest_candidates(root_dir=root_dir)

    def add_files(self, file_paths: list[str | Path], tags: list[str] | None = None) -> IngestSummary:
        import time

        started = time.perf_counter()
        results = [self._process_one_file(Path(raw_path), tags or []) for raw_path in file_paths]

        self.vector_store.flush()
        elapsed_ms = (time.perf_counter() - started) * 1000

        indexed_files = sum(1 for r in results if r.status == "indexed")
        skipped_files = sum(1 for r in results if r.status == "skipped")
        failed_files = sum(1 for r in results if r.status == "failed")
        total_chunks = sum(r.chunk_count for r in results)

        if total_chunks > 500:
            logger.info(
                "Imported %d chunks across %d files in %.0fms — "
                "consider raising CHUNK_SIZE for fewer chunks with larger files.",
                total_chunks, indexed_files, elapsed_ms,
            )
        return IngestSummary(
            total_files=len(file_paths),
            indexed_files=indexed_files,
            skipped_files=skipped_files,
            failed_files=failed_files,
            total_chunks=total_chunks,
            elapsed_ms=elapsed_ms,
            results=results,
        )

    def _process_one_file(self, path: Path, tags: list[str]) -> FileIngestResult:
        """处理单个文件：检查→提取→分块→嵌入→持久化→更新 manifest。"""
        source_path = self._display_path(path)
        document_id = build_document_id(source_path)

        skip_result = self._skip_missing_or_unsupported(path, source_path, document_id)
        if skip_result:
            return skip_result

        try:
            file_bytes = path.read_bytes()
            content_hash = sha256_bytes(file_bytes)
            existing = self.manifest.find_by_path(source_path)

            skip_hash = self._skip_unchanged(existing, content_hash, source_path, document_id)
            if skip_hash:
                return skip_hash

            text = self._extract_text(path, file_bytes, path.suffix.lower())
            normalized = normalize_text(text)
            if not normalized:
                raise ValueError("File is empty after normalization")

            if existing:
                self.vector_store.delete_by_document_id(document_id)

            chunks = self._build_chunks(
                text=normalized, path=path, source_path=source_path,
                document_id=document_id, content_hash=content_hash, tags=tags,
            )
            self._embed_and_store(chunks)
            self._write_manifest(source_path, path, document_id, content_hash, chunks, existing, tags)

            return FileIngestResult(
                path=source_path, status="indexed",
                document_id=document_id, chunk_count=len(chunks),
            )
        except Exception as exc:
            self.manifest.mark_failed(source_path, str(exc), document_id=document_id)
            return FileIngestResult(
                path=source_path, status="failed",
                document_id=document_id, error=str(exc),
            )

    def _skip_missing_or_unsupported(self, path: Path, source_path: str, document_id: str) -> FileIngestResult | None:
        """检查文件是否存在、扩展名是否支持。返回 skip/fail 结果，或 None 表示可继续。"""
        if not path.exists() or not path.is_file():
            self.manifest.mark_failed(source_path, "File does not exist", document_id=document_id)
            return FileIngestResult(path=source_path, status="failed", document_id=document_id, error="File does not exist")

        if path.suffix.lower() not in set(self.config.supported_extensions):
            return FileIngestResult(
                path=source_path, status="skipped", document_id=document_id,
                error=f"Unsupported file type: {path.suffix.lower()}",
            )
        return None

    def _skip_unchanged(self, existing: dict[str, Any] | None, content_hash: str, source_path: str, document_id: str) -> FileIngestResult | None:
        """检查文件内容是否未变。未变时返回 skip 结果，否则返回 None。"""
        if existing and existing.get("content_hash") == content_hash and existing.get("status") == "indexed":
            return FileIngestResult(
                path=source_path, status="skipped", document_id=document_id,
                chunk_count=existing.get("chunk_count", 0),
            )
        return None

    def _embed_and_store(self, chunks: list[ChunkRecord]) -> None:
        """为所有 chunk 生成嵌入并写入 vector store。"""
        embeddings = self._embed_chunks([chunk.text for chunk in chunks])
        for chunk, embedding in zip(chunks, embeddings):
            chunk.embedding = embedding
        self.vector_store.upsert_chunks(chunks)

    def _write_manifest(self, source_path: str, path: Path, document_id: str, content_hash: str,
                        chunks: list[ChunkRecord], existing: dict[str, Any] | None, tags: list[str]) -> None:
        """将索引结果写入 manifest。"""
        now = utc_now_iso()
        record = {
            "document_id": document_id,
            "source_path": source_path,
            "file_name": path.name,
            "file_ext": path.suffix.lower(),
            "content_hash": content_hash,
            "mtime": path.stat().st_mtime,
            "size_bytes": path.stat().st_size,
            "chunk_count": len(chunks),
            "tags": tags,
            "status": "indexed",
            "created_at": existing.get("created_at", now) if existing else now,
            "updated_at": now,
            "last_error": None,
        }
        self.manifest.upsert_document(record)

    def rebuild_index(self, force: bool = False) -> IngestSummary:
        import logging as _logging

        logger = _logging.getLogger(__name__)
        if force:
            logger.info("Force-rebuilding index — clearing all data first")
            self.clear_index(clear_manifest=True)

        existing_paths = {record["source_path"]: record for record in self.manifest.list_documents()}
        current_files = self.scan_files()
        current_paths = {self._display_path(path) for path in current_files}

        removed_count = 0
        for source_path, record in existing_paths.items():
            if source_path in current_paths:
                continue
            self.vector_store.delete_by_document_id(record["document_id"])
            self.manifest.remove_document(record["document_id"])
            removed_count += 1

        if removed_count:
            logger.info("Removed %d stale document(s) from index", removed_count)

        summary = self.add_files(current_files)
        if summary.failed_files:
            logger.warning(
                "Rebuild finished with %d/%d files failed",
                summary.failed_files,
                summary.total_files,
            )
        return summary

    def delete_file(self, document_id_or_path: str, delete_source: bool = False) -> FileIngestResult:
        record = self.manifest.get(document_id_or_path)
        if record is None:
            record = self.manifest.find_by_path(document_id_or_path)
        if record is None:
            raise ValueError(f"Document not found: {document_id_or_path}")

        document_id = record["document_id"]
        source_path = record["source_path"]
        removed = self.vector_store.delete_by_document_id(document_id)
        self.manifest.remove_document(document_id)

        path = Path(source_path)
        if delete_source and path.exists():
            path.unlink()

        return FileIngestResult(
            path=source_path,
            status="deleted",
            document_id=document_id,
            chunk_count=removed,
        )

    def clear_index(self, clear_manifest: bool = True) -> None:
        self.vector_store.clear()
        if clear_manifest:
            self.manifest.clear()

    def get_index_stats(self) -> dict[str, Any]:
        documents = self.manifest.list_documents()
        indexed = [record for record in documents if record.get("status") == "indexed"]
        failed = [record for record in documents if record.get("status") == "failed"]
        last_updated_at = max((record.get("updated_at", "") for record in documents), default="")
        return {
            "document_count": len(documents),
            "indexed_document_count": len(indexed),
            "failed_document_count": len(failed),
            "missing_document_count": 0,
            "chunk_count": self.vector_store.count_chunks(),
            "collection_name": "knowledge_base",
            "vectorstore_path": str(self.co_dir / "vectordb"),
            "last_updated_at": last_updated_at,
        }

    def list_documents(self) -> list[dict[str, Any]]:
        documents = self.manifest.list_documents()
        return sorted(documents, key=lambda item: item.get("updated_at", ""), reverse=True)

    def update_document_tags(self, document_id: str, tags: list[str]) -> dict[str, Any] | None:
        """更新指定文档的 tags 并返回更新后的记录。"""
        return self.manifest.update_tags(document_id, tags)

    def _build_chunks(
        self,
        text: str,
        path: Path,
        source_path: str,
        document_id: str,
        content_hash: str,
        tags: list[str],
    ) -> list[ChunkRecord]:
        spans = self._split_text(text)
        chunks: list[ChunkRecord] = []
        for index, chunk_text in enumerate(spans):
            chunk_id = f"{document_id}:{index:04d}"
            metadata = {
                "chunk_id": chunk_id,
                "document_id": document_id,
                "source_path": source_path,
                "file_name": path.name,
                "file_ext": path.suffix.lower(),
                "chunk_index": index,
                "chunk_count": len(spans),
                "content_hash": content_hash,
                "tags": tags,
            }
            chunks.append(ChunkRecord(chunk_id=chunk_id, document_id=document_id, text=chunk_text, metadata=metadata))
        return chunks

    def _split_text(self, text: str) -> list[str]:
        target_chars = self.config.chunk_size
        overlap_chars = self.config.chunk_overlap

        if len(text) <= target_chars:
            return [text]

        chunks: list[str] = []
        start = 0
        while start < len(text):
            remaining = len(text) - start
            if remaining <= target_chars:
                chunk = text[start:].strip()
                if chunk:
                    chunks.append(chunk)
                break

            end = start + target_chars

            # Prefer paragraph breaks, then line breaks
            paragraph_break = text.rfind("\n\n", start + 1, end)
            if paragraph_break > start and paragraph_break - start >= target_chars // 2:
                end = paragraph_break
            else:
                line_break = text.rfind("\n", start + 1, end)
                if line_break > start and line_break - start >= target_chars // 2:
                    end = line_break

            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            if end >= len(text):
                break

            # Compute overlap start within [end - overlap_chars, end)
            # The overlap window is the last O characters of the just-extracted
            # chunk.  The next chunk starts somewhere inside this window so the
            # boundaries of adjacent chunks overlap by (up to) overlap_chars.
            overlap_window_start = max(end - overlap_chars, 0)
            if overlap_window_start >= end:
                overlap_window_start = end - 1

            overlap_start = overlap_window_start
            if overlap_window_start < len(text):
                # Search for a clean break point *within* the overlap window
                next_paragraph = text.find("\n\n", overlap_window_start)
                if overlap_window_start <= next_paragraph < end:
                    overlap_start = next_paragraph + 2
                else:
                    next_line = text.find("\n", overlap_window_start)
                    if overlap_window_start <= next_line < end:
                        overlap_start = next_line + 1

            # Safety guard: always make forward progress
            # Use at least 25% of target_chars to prevent degenerate tiny chunks
            min_progress = max(1, target_chars // 4)
            start = max(overlap_start, start + min_progress)

        return chunks

    def _extract_text(self, path: Path, file_bytes: bytes, file_ext: str) -> str:
        parser = self.parser_registry.get(file_ext)
        if parser is None:
            raise ValueError(f"No parser registered for extension: {file_ext}")
        return parser.parse(file_bytes, file_ext)

    def _embed_chunks(self, texts: list[str]) -> list[list[float] | None]:
        if not texts:
            return []
        if self.embedding_model is None:
            return [None for _ in texts]
        if hasattr(self.embedding_model, "get_text_embedding_batch"):
            return list(self.embedding_model.get_text_embedding_batch(texts))
        if hasattr(self.embedding_model, "embed_batch"):
            return list(self.embedding_model.embed_batch(texts))
        raise TypeError("Embedding model does not support batch embeddings")

    def _display_path(self, path: Path) -> str:
        try:
            return path.relative_to(self.root).as_posix()
        except ValueError:
            return path.as_posix()
