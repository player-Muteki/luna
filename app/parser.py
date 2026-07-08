from __future__ import annotations

import io
import logging
from abc import ABC, abstractmethod
from pathlib import Path

logger = logging.getLogger(__name__)

# 向后兼容 — 实现见 core/parser.py
from core.parser import (
    DocumentParser,
    TextParser,
    PDFParser,
    DocxParser,
    PPTXParser,
    TEXT_EXTENSIONS,
    PARSER_REGISTRY,
    MAX_BINARY_FILE_BYTES,
)

__all__ = [
    "DocumentParser",
    "TextParser",
    "PDFParser",
    "DocxParser",
    "PPTXParser",
    "TEXT_EXTENSIONS",
    "PARSER_REGISTRY",
    "MAX_BINARY_FILE_BYTES",
]
