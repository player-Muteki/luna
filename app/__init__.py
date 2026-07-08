"""向后兼容层 — 核心模块已迁移至 core/。"""
from __future__ import annotations

from core.chat_engine import ChatEngine, Conversation, Message
from core.generator import GenerationResult, RAGGenerator, SourceReference
from core.ingest import (
    ChunkRecord,
    FileIngestResult,
    IngestionEngine,
    IngestSummary,
    VectorStore,
)
from core.parser import (
    DocxParser,
    DocumentParser,
    PARSER_REGISTRY,
    PDFParser,
    PPTXParser,
    TEXT_EXTENSIONS,
    TextParser,
)
from core.retriever import (
    HybridRetriever,
    RetrievalResult,
    RetrievalResults,
)

__all__ = [
    "ChatEngine",
    "ChunkRecord",
    "Conversation",
    "DocumentParser",
    "DocxParser",
    "FileIngestResult",
    "GenerationResult",
    "HybridRetriever",
    "IngestionEngine",
    "IngestSummary",
    "Message",
    "PARSER_REGISTRY",
    "PDFParser",
    "PPTXParser",
    "RAGGenerator",
    "RetrievalResult",
    "RetrievalResults",
    "SourceReference",
    "TEXT_EXTENSIONS",
    "TextParser",
    "VectorStore",
]
