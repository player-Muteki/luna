from __future__ import annotations

import hashlib
import json
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import Settings, ensure_directories

SUPPORTED_EXTENSIONS = {
    ".c",
    ".cpp",
    ".cs",
    ".go",
    ".h",
    ".java",
    ".js",
    ".jsx",
    ".md",
    ".mdx",
    ".php",
    ".py",
    ".rb",
    ".rs",
    ".ts",
    ".tsx",
    ".txt",
}

SKIP_DIR_NAMES = {".git", ".hg", ".svn", "__pycache__", "vectorstore", "storage"}


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
        tmp_path = self.path.with_suffix(f"{self.path.suffix}.tmp")
        tmp_path.write_text(
            json.dumps(self.data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        tmp_path.replace(self.path)

    def clear(self) -> None:
        self.data = {"version": 1, "documents": {}}
        self.save()

    def upsert_document(self, record: dict[str, Any]) -> None:
        self.data["documents"][record["document_id"]] = record
        self.save()

    def mark_failed(self, source_path: str, error: str, document_id: str | None = None) -> None:
        existing = self.find_by_path(source_path)
        doc_id = document_id or (existing or {}).get("document_id") or build_document_id(source_path)
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


class VectorStore(ABC):
    """Abstract interface for vector/chunk storage.

    Implementations must provide chunk-level CRUD and iteration.
    """

    @abstractmethod
    def upsert_chunks(self, chunks: list[ChunkRecord]) -> None: ...

    @abstractmethod
    def delete_by_document_id(self, document_id: str) -> int: ...

    @abstractmethod
    def clear(self) -> None: ...

    @abstractmethod
    def count_chunks(self) -> int: ...

    @abstractmethod
    def count_documents(self) -> int: ...

    @abstractmethod
    def iter_records(self) -> list[dict[str, Any]]: ...

    @abstractmethod
    def get_record(self, chunk_id: str) -> dict[str, Any] | None: ...


class JsonVectorStore(VectorStore):
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
        tmp_path = self.path.with_suffix(f"{self.path.suffix}.tmp")
        tmp_path.write_text(
            json.dumps(self.records, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        tmp_path.replace(self.path)

    def upsert_chunks(self, chunks: list[ChunkRecord]) -> None:
        for chunk in chunks:
            self.records[chunk.chunk_id] = asdict(chunk)
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
    def __init__(self, settings: Settings, embedding_model: Any | None = None, vector_store: Any | None = None):
        self.settings = settings
        ensure_directories(settings)
        self.embedding_model = embedding_model
        self.vector_store = vector_store or JsonVectorStore(settings.vectorstore_dir / "chunks.json")
        self.manifest = DocumentManifest(settings.storage_dir / "document_manifest.json")

    def scan_files(self, root_dir: str | Path | None = None) -> list[Path]:
        root = Path(root_dir) if root_dir is not None else self.settings.data_dir
        if not root.exists():
            return []
        files: list[Path] = []
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if any(part.startswith(".") for part in path.parts):
                continue
            if any(part in SKIP_DIR_NAMES for part in path.parts):
                continue
            if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                continue
            files.append(path)
        return sorted(files)

    def add_files(self, file_paths: list[str | Path], tags: list[str] | None = None) -> IngestSummary:
        import time

        started = time.perf_counter()
        results: list[FileIngestResult] = []
        indexed_files = 0
        skipped_files = 0
        failed_files = 0
        total_chunks = 0

        for raw_path in file_paths:
            path = Path(raw_path)
            source_path = self._display_path(path)
            document_id = build_document_id(source_path)

            if not path.exists() or not path.is_file():
                failed_files += 1
                error = "File does not exist"
                self.manifest.mark_failed(source_path, error, document_id=document_id)
                results.append(FileIngestResult(path=source_path, status="failed", document_id=document_id, error=error))
                continue

            if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                skipped_files += 1
                results.append(
                    FileIngestResult(
                        path=source_path,
                        status="skipped",
                        document_id=document_id,
                        error=f"Unsupported file type: {path.suffix.lower()}",
                    )
                )
                continue

            try:
                file_bytes = path.read_bytes()
                content_hash = sha256_bytes(file_bytes)
                existing = self.manifest.find_by_path(source_path)
                if existing and existing.get("content_hash") == content_hash and existing.get("status") == "indexed":
                    skipped_files += 1
                    results.append(
                        FileIngestResult(
                            path=source_path,
                            status="skipped",
                            document_id=document_id,
                            chunk_count=existing.get("chunk_count", 0),
                        )
                    )
                    continue

                text = self._decode_text(file_bytes)
                normalized = normalize_text(text)
                if not normalized:
                    raise ValueError("File is empty after normalization")

                if existing:
                    self.vector_store.delete_by_document_id(document_id)

                chunks = self._build_chunks(
                    text=normalized,
                    path=path,
                    source_path=source_path,
                    document_id=document_id,
                    content_hash=content_hash,
                    tags=tags or [],
                )
                embeddings = self._embed_chunks([chunk.text for chunk in chunks])
                for chunk, embedding in zip(chunks, embeddings):
                    chunk.embedding = embedding

                self.vector_store.upsert_chunks(chunks)
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
                    "tags": tags or [],
                    "status": "indexed",
                    "created_at": existing.get("created_at", now) if existing else now,
                    "updated_at": now,
                    "last_error": None,
                }
                self.manifest.upsert_document(record)

                indexed_files += 1
                total_chunks += len(chunks)
                results.append(
                    FileIngestResult(
                        path=source_path,
                        status="indexed",
                        document_id=document_id,
                        chunk_count=len(chunks),
                    )
                )
            except Exception as exc:
                failed_files += 1
                self.manifest.mark_failed(source_path, str(exc), document_id=document_id)
                results.append(
                    FileIngestResult(
                        path=source_path,
                        status="failed",
                        document_id=document_id,
                        error=str(exc),
                    )
                )

        elapsed_ms = (time.perf_counter() - started) * 1000
        return IngestSummary(
            total_files=len(file_paths),
            indexed_files=indexed_files,
            skipped_files=skipped_files,
            failed_files=failed_files,
            total_chunks=total_chunks,
            elapsed_ms=elapsed_ms,
            results=results,
        )

    def rebuild_index(self, force: bool = False) -> IngestSummary:
        if force:
            self.clear_index(clear_manifest=True)

        existing_paths = {record["source_path"]: record for record in self.manifest.list_documents()}
        current_files = self.scan_files()
        current_paths = {self._display_path(path) for path in current_files}

        for source_path, record in existing_paths.items():
            if source_path in current_paths:
                continue
            self.vector_store.delete_by_document_id(record["document_id"])
            self.manifest.remove_document(record["document_id"])

        return self.add_files(current_files)

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
            "vectorstore_path": str(self.settings.vectorstore_dir),
            "last_updated_at": last_updated_at,
        }

    def list_documents(self) -> list[dict[str, Any]]:
        documents = self.manifest.list_documents()
        return sorted(documents, key=lambda item: item.get("updated_at", ""), reverse=True)

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

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """Estimate token count without external tokenizer.

        Rough heuristic: ~4 bytes per token for ASCII, ~2.5 bytes per token
        for mixed CJK/Latin text. This is intentionally approximate.
        """
        if not text:
            return 0
        byte_len = len(text.encode("utf-8"))
        return max(1, byte_len // 3)

    def _split_text(self, text: str) -> list[str]:
        target_chars = self.settings.chunk_size
        overlap_chars = self.settings.chunk_overlap

        # If the entire text fits within one chunk, return as-is
        if len(text) <= target_chars:
            return [text]

        # Prefer paragraph breaks, then line breaks, then character-level split
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

            # Try to find a paragraph break (\n\n) before end
            paragraph_break = text.rfind("\n\n", start + 1, end)
            if paragraph_break > start and paragraph_break - start >= target_chars // 2:
                end = paragraph_break
            else:
                # Try to find a line break (\n) before end
                line_break = text.rfind("\n", start + 1, end)
                if line_break > start and line_break - start >= target_chars // 2:
                    end = line_break
                # else: keep end at character boundary

            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            if end >= len(text):
                break

            # Compute overlap start — try to start at a line/paragraph break
            overlap_start = max(end - overlap_chars, start + 1)
            if overlap_start < len(text):
                next_paragraph = text.find("\n\n", overlap_start)
                if 0 < next_paragraph < end + overlap_chars:
                    overlap_start = next_paragraph + 2
                elif overlap_start < len(text):
                    next_line = text.find("\n", overlap_start)
                    if 0 < next_line < end + overlap_chars:
                        overlap_start = next_line + 1
            start = overlap_start

        return chunks

    def _decode_text(self, file_bytes: bytes) -> str:
        encodings = ("utf-8", "utf-8-sig", "gb18030", "latin-1")
        last_error: Exception | None = None
        for encoding in encodings:
            try:
                return file_bytes.decode(encoding)
            except UnicodeDecodeError as exc:
                last_error = exc
        if last_error is not None:
            raise last_error
        raise ValueError("Unable to decode file")

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
            return str(path.relative_to(Path.cwd()))
        except ValueError:
            return str(path)
