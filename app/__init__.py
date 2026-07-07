"""Application package for Co-Thinker — a RAG-based Q&A system."""

from app.chat_engine import ChatEngine, Conversation, Message
from app.generator import GenerationResult, RAGGenerator, SourceReference
from app.ingest import (
    ChunkRecord,
    DocumentManifest,
    FileIngestResult,
    IngestionEngine,
    IngestSummary,
    JsonVectorStore,
    VectorStore,
)
from app.retriever import (
    HybridRetriever,
    RetrievalResult,
    RetrievalResults,
)
from config import Settings

__all__ = [
    "ChatEngine",
    "ChunkRecord",
    "Conversation",
    "DocumentManifest",
    "FileIngestResult",
    "GenerationResult",
    "HybridRetriever",
    "IngestionEngine",
    "IngestSummary",
    "JsonVectorStore",
    "Message",
    "RAGGenerator",
    "RetrievalResult",
    "RetrievalResults",
    "Settings",
    "SourceReference",
    "VectorStore",
]
