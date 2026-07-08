from __future__ import annotations

import math
import re
import time
from dataclasses import dataclass, field
from typing import Any

from core.ingest import VectorStore
from core.project import ProjectConfig

# Match English/alphanumeric tokens as words, Chinese characters individually.
# Single-char Chinese tokenization ensures partial overlap (e.g. query "红黑树"
# and chunk "红黑树的性质" share "红", "黑", "树"), which the greedy + pattern
# could not provide (both became monolithic single tokens).
# CJK Unified Ideographs: U+4E00–U+9FFF (基本区)
# CJK Extension A: U+3400–U+4DBF
# CJK Extension B: U+20000–U+2A6DF (需要代理对支持的补充平面字符)
# 这里覆盖基本区和 Extension A , 覆盖 ~98% 常见汉字
TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_./:-]+|[\u4e00-\u9fff\u3400-\u4dbf]")
SHORT_QUERY_HINTS = {"它", "这个", "这个功能", "这些", "那个", "有哪些", "怎么做", "如何", "为什么"}


@dataclass
class RetrievalResult:
    chunk_id: str
    document_id: str
    text: str
    source_path: str
    file_name: str
    metadata: dict[str, Any] = field(default_factory=dict)
    vector_score: float | None = None
    bm25_score: float | None = None
    rrf_score: float | None = None
    final_score: float = 0.0
    matched_by: list[str] = field(default_factory=list)
    rank_details: dict[str, int] = field(default_factory=dict)


@dataclass
class RetrievalResults:
    original_query: str
    effective_query: str
    results: list[RetrievalResult]
    mode: str
    total_candidates: int
    elapsed_ms: float
    filters: dict[str, Any] = field(default_factory=dict)

    def top_k(self, k: int) -> list[RetrievalResult]:
        return self.results[:k]

    def to_context_text(self, token_budget: int | None = None) -> str:
        limit = token_budget or 6000
        sections: list[str] = []
        used = 0
        for index, result in enumerate(self.results, start=1):
            header = (
                f"[chunk: {index}]\n"
                f"source: {result.source_path}\n"
                f"chunk_id: {result.chunk_id}\n"
                f"score: {result.final_score:.4f}\n"
                "content:\n"
            )
            remaining = max(limit - used - len(header), 0)
            if remaining <= 0:
                break
            content = result.text
            if len(content) > remaining:
                content = content[: max(0, remaining - 8)].rstrip() + "\n[截断]"
            block = header + content
            sections.append(block)
            used += len(block) + 2
            if used >= limit:
                break
        return "\n\n".join(sections)

    def to_sources(self) -> list[dict[str, Any]]:
        return [
            {
                "chunk_id": item.chunk_id,
                "document_id": item.document_id,
                "source_path": item.source_path,
                "file_name": item.file_name,
                "score": item.final_score,
                "matched_by": item.matched_by,
            }
            for item in self.results
        ]

    @property
    def confidence(self) -> str:
        if not self.results:
            return "none"
        top = self.results[0].final_score
        # Scores are normalized to [0, 1] for all retrieval modes
        if top >= 0.5:
            return "high"
        if top >= 0.25:
            return "medium"
        return "low"


class HybridRetriever:
    def __init__(
        self,
        config: ProjectConfig,
        vector_store: VectorStore,
        embedding_model: Any | None = None,
        bm25_retriever: Any | None = None,
        query_rewriter: Any | None = None,
    ):
        self.config = config
        self.vector_store = vector_store
        self.embedding_model = embedding_model
        self.bm25_retriever = bm25_retriever
        self.query_rewriter = query_rewriter
        # BM25 IDF cache — invalidated when record count changes
        self._idf_cache: dict[str, float] | None = None
        self._idf_avgdl: float = 0.0
        self._idf_n: int = 0

    def retrieve(
        self,
        query: str,
        chat_history: list[dict[str, Any]] | None = None,
        mode: str = "hybrid",
        top_k: int | None = None,
        filters: dict[str, Any] | None = None,
    ) -> RetrievalResults:
        started = time.perf_counter()
        filters = filters or {}
        effective_query = self.preprocess_query(query, chat_history)
        candidate_k = self.config.retrieval_candidate_k

        vector_results: list[RetrievalResult] = []
        bm25_results: list[RetrievalResult] = []

        if mode in {"hybrid", "vector"}:
            vector_results = self.vector_retrieve(effective_query, candidate_k, filters=filters)
        if mode in {"hybrid", "bm25"}:
            bm25_results = self.bm25_retrieve(effective_query, candidate_k, filters=filters)

        if mode == "vector":
            results = vector_results
        elif mode == "bm25":
            results = bm25_results
        else:
            results = self.fuse_results(vector_results, bm25_results)

        final_top_k = top_k or self.config.top_k
        elapsed_ms = (time.perf_counter() - started) * 1000
        return RetrievalResults(
            original_query=query,
            effective_query=effective_query,
            results=results[:final_top_k],
            mode=mode,
            total_candidates=len(results),
            elapsed_ms=elapsed_ms,
            filters=filters,
        )

    def preprocess_query(self, query: str, chat_history: list[dict[str, Any]] | None = None) -> str:
        normalized = " ".join(query.strip().split())
        if not normalized:
            return ""
        if self.query_rewriter is not None and chat_history:
            rewritten = self.query_rewriter.rewrite(normalized, chat_history)
            if rewritten:
                return rewritten
        if self._needs_history_context(normalized) and chat_history:
            last_user = self._last_user_message(chat_history)
            if last_user:
                return f"{last_user} {normalized}"
        return normalized

    def vector_retrieve(
        self,
        query: str,
        candidate_k: int,
        filters: dict[str, Any] | None = None,
    ) -> list[RetrievalResult]:
        filters = filters or {}
        query_tokens = tokenize(query)
        query_embedding = self._query_embedding(query)
        results: list[RetrievalResult] = []

        for record in self._iter_records(filters):
            vector_score = self._vector_score(query_tokens, query_embedding, record)
            if vector_score < self.config.similarity_cutoff:
                continue
            result = self._record_to_result(record)
            result.vector_score = vector_score
            result.final_score = vector_score
            result.matched_by.append("vector")
            results.append(result)

        results.sort(key=lambda item: item.vector_score or 0.0, reverse=True)
        for rank, result in enumerate(results, start=1):
            result.rank_details["vector"] = rank
        return results[:candidate_k]

    def bm25_retrieve(
        self,
        query: str,
        candidate_k: int,
        filters: dict[str, Any] | None = None,
    ) -> list[RetrievalResult]:
        filters = filters or {}
        query_tokens = tokenize(query)
        records = self._iter_records(filters)

        # Pre-tokenize all records once so IDF build and BM25 scoring share the
        # work.  Store tokens in a parallel dict keyed by id() to avoid mutating
        # the underlying records dict (which may be shared with other components
        # such as the vector store).
        _token_cache: dict[int, list[str]] = {}
        for record in records:
            _token_cache[id(record)] = tokenize(self._record_haystack(record))

        idf, avgdl = self._get_or_build_idf(records)

        results: list[RetrievalResult] = []
        for record in records:
            score = self._bm25_score(query_tokens, record, idf, avgdl=avgdl, token_cache=_token_cache)
            if score <= 0:
                continue
            result = self._record_to_result(record)
            result.bm25_score = score
            result.final_score = score
            result.matched_by.append("bm25")
            results.append(result)

        results.sort(key=lambda item: item.bm25_score or 0.0, reverse=True)
        for rank, result in enumerate(results, start=1):
            result.rank_details["bm25"] = rank
        return results[:candidate_k]

    def fuse_results(
        self,
        vector_results: list[RetrievalResult],
        bm25_results: list[RetrievalResult],
    ) -> list[RetrievalResult]:
        merged: dict[str, RetrievalResult] = {}

        for rank, result in enumerate(vector_results, start=1):
            item = merged.setdefault(result.chunk_id, self._clone_result(result))
            item.vector_score = result.vector_score
            if "vector" not in item.matched_by:
                item.matched_by.append("vector")
            item.rank_details["vector"] = rank
            item.rrf_score = (item.rrf_score or 0.0) + self.config.vector_weight / (self.config.rrf_k + rank)

        for rank, result in enumerate(bm25_results, start=1):
            item = merged.setdefault(result.chunk_id, self._clone_result(result))
            item.bm25_score = result.bm25_score
            if "bm25" not in item.matched_by:
                item.matched_by.append("bm25")
            item.rank_details["bm25"] = rank
            item.rrf_score = (item.rrf_score or 0.0) + self.config.bm25_weight / (self.config.rrf_k + rank)

        fused = list(merged.values())
        for item in fused:
            # Normalize RRF score to [0, 1] so it's comparable with raw scores:
            # max_possible = vector_weight/(rrf_k+1) + bm25_weight/(rrf_k+1) = 1/(rrf_k+1)
            # Multiply by (rrf_k + 1) to rescale to [0, 1]
            rrf = item.rrf_score or 0.0
            if rrf > 0 and item.matched_by:
                rrf_normalized = rrf * (self.config.rrf_k + 1)
                item.final_score = min(rrf_normalized, 1.0)
            else:
                item.final_score = item.vector_score or item.bm25_score or 0.0
        fused.sort(key=lambda item: item.final_score, reverse=True)
        return fused

    def _iter_records(self, filters: dict[str, Any]) -> list[dict[str, Any]]:
        if hasattr(self.vector_store, "iter_records"):
            records = self.vector_store.iter_records()
        else:
            # Fallback for non-standard vector stores
            records = list(getattr(self.vector_store, "records", {}).values())
        return [record for record in records if self._matches_filters(record, filters)]

    def _matches_filters(self, record: dict[str, Any], filters: dict[str, Any]) -> bool:
        metadata = record.get("metadata", {})
        if not filters:
            return True
        file_ext = filters.get("file_ext")
        if file_ext and metadata.get("file_ext") != file_ext:
            return False
        source_path = filters.get("source_path")
        if source_path and metadata.get("source_path") != source_path:
            return False
        tag = filters.get("tag")
        if tag and tag not in metadata.get("tags", []):
            return False
        return True

    def _record_to_result(self, record: dict[str, Any]) -> RetrievalResult:
        metadata = record.get("metadata", {})
        return RetrievalResult(
            chunk_id=record["chunk_id"],
            document_id=record["document_id"],
            text=record["text"],
            source_path=metadata.get("source_path", ""),
            file_name=metadata.get("file_name", ""),
            metadata=metadata,
        )

    def _clone_result(self, result: RetrievalResult) -> RetrievalResult:
        return RetrievalResult(
            chunk_id=result.chunk_id,
            document_id=result.document_id,
            text=result.text,
            source_path=result.source_path,
            file_name=result.file_name,
            metadata=dict(result.metadata),
            vector_score=result.vector_score,
            bm25_score=result.bm25_score,
            rrf_score=result.rrf_score,
            final_score=result.final_score,
            matched_by=list(result.matched_by),
            rank_details=dict(result.rank_details),
        )

    def _query_embedding(self, query: str) -> list[float] | None:
        if self.embedding_model is None:
            return None
        if hasattr(self.embedding_model, "get_query_embedding"):
            return self.embedding_model.get_query_embedding(query)
        if hasattr(self.embedding_model, "get_text_embedding"):
            return self.embedding_model.get_text_embedding(query)
        return None

    def _vector_score(self, query_tokens: list[str], query_embedding: list[float] | None, record: dict[str, Any]) -> float:
        if query_embedding is not None and record.get("embedding"):
            return cosine_similarity(query_embedding, record["embedding"])

        text_tokens = tokenize(record.get("text", ""))
        if not query_tokens or not text_tokens:
            return 0.0
        intersection = len(set(query_tokens) & set(text_tokens))
        return intersection / max(len(set(query_tokens)), 1)

    def invalidate_idf_cache(self) -> None:
        """Force IDF cache to rebuild on next BM25 query.

        Call this after ingesting or removing documents.
        """
        self._idf_cache = None
        self._idf_avgdl = 0.0
        self._idf_n = 0

    def _get_or_build_idf(self, records: list[dict[str, Any]]) -> tuple[dict[str, float], float]:
        """Return cached IDF + avgdl if record count unchanged, else rebuild."""
        if self._idf_cache is not None and len(records) == self._idf_n:
            return self._idf_cache, self._idf_avgdl

        # Build IDF
        N = len(records)
        if N == 0:
            self._idf_cache = {}
            self._idf_avgdl = 0.0
            self._idf_n = 0
            return self._idf_cache, self._idf_avgdl

        df: dict[str, int] = {}
        total_dl = 0
        for record in records:
            haystack = self._record_haystack(record)
            tokens = tokenize(haystack)
            total_dl += len(tokens)
            seen = set(tokens)
            for token in seen:
                df[token] = df.get(token, 0) + 1

        avgdl = total_dl / max(N, 1)
        idf: dict[str, float] = {}
        for token, doc_count in df.items():
            idf[token] = math.log(1.0 + (N - doc_count + 0.5) / (doc_count + 0.5))

        self._idf_cache = idf
        self._idf_avgdl = avgdl
        self._idf_n = N
        return self._idf_cache, self._idf_avgdl

    def _bm25_score(
        self,
        query_tokens: list[str],
        record: dict[str, Any],
        idf: dict[str, float],
        k1: float = 1.5,
        b: float = 0.75,
        avgdl: float = 100.0,
        token_cache: dict[int, list[str]] | None = None,
    ) -> float:
        """Compute BM25 Okapi score for a single record given pre-computed IDF.

        BM25(tf) = idf * (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * (dl / avgdl)))
        """
        if not query_tokens:
            return 0.0

        # Reuse pre-tokenized tokens when available (from BM25 pre-tokenization or IDF build)
        tokens = None
        if token_cache is not None:
            tokens = token_cache.get(id(record))
        if tokens is None:
            tokens = tokenize(self._record_haystack(record))

        if not tokens:
            return 0.0

        dl = len(tokens)
        tf: dict[str, int] = {}
        for token in tokens:
            tf[token] = tf.get(token, 0) + 1

        score = 0.0
        for token in query_tokens:
            token_tf = tf.get(token, 0)
            if token_tf == 0:
                continue
            token_idf = idf.get(token, 1.0)
            tf_norm = (token_tf * (k1 + 1)) / (token_tf + k1 * (1 - b + b * dl / avgdl))
            score += token_idf * tf_norm
        return score

    @staticmethod
    def _record_haystack(record: dict[str, Any]) -> str:
        """Build the haystack string for a record (text + metadata fields)."""
        text = record.get("text", "")
        metadata = record.get("metadata", {})
        return " ".join(
            filter(None, [
                text,
                metadata.get("source_path", ""),
                metadata.get("file_name", ""),
                " ".join(metadata.get("tags", [])),
            ])
        )

    def _needs_history_context(self, query: str) -> bool:
        compact = query.strip()
        return len(compact) <= 12 or any(hint in compact for hint in SHORT_QUERY_HINTS)

    def _last_user_message(self, chat_history: list[dict[str, Any]]) -> str:
        for message in reversed(chat_history):
            if message.get("role") == "user" and message.get("content"):
                return str(message["content"]).strip()
        return ""


def tokenize(text: str) -> list[str]:
    return [match.group(0).lower() for match in TOKEN_PATTERN.finditer(text)]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    numerator = sum(x * y for x, y in zip(a, b))
    left = math.sqrt(sum(x * x for x in a))
    right = math.sqrt(sum(y * y for y in b))
    if left < 1e-12 or right < 1e-12:
        return 0.0
    return numerator / (left * right)