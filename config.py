from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional during early bootstrap
    load_dotenv = None


def _load_env_file() -> None:
    if load_dotenv is not None:
        load_dotenv()


def _get_str(name: str, default: str) -> str:
    value = os.getenv(name)
    return default if value is None else value


def _get_int(name: str, default: int) -> int:
    value = os.getenv(name)
    return default if value in (None, "") else int(value)


def _get_float(name: str, default: float) -> float:
    value = os.getenv(name)
    return default if value in (None, "") else float(value)


@dataclass(frozen=True)
class Settings:
    deepseek_api_key: str
    deepseek_base_url: str
    deepseek_model: str
    data_dir: Path
    vectorstore_dir: Path
    storage_dir: Path
    chunk_size: int
    chunk_overlap: int
    top_k: int
    retrieval_candidate_k: int
    similarity_cutoff: float
    rrf_k: int
    vector_weight: float
    bm25_weight: float
    max_tokens: int
    temperature: float
    context_token_budget: int
    max_history_turns: int
    log_level: str


def load_settings(overrides: dict[str, Any] | None = None) -> Settings:
    _load_env_file()
    settings = Settings(
        deepseek_api_key=_get_str("DEEPSEEK_API_KEY", ""),
        deepseek_base_url=_get_str("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        deepseek_model=_get_str("DEEPSEEK_MODEL", "deepseek-chat"),
        data_dir=Path(_get_str("DATA_DIR", "data")),
        vectorstore_dir=Path(_get_str("VECTORSTORE_DIR", "vectorstore")),
        storage_dir=Path(_get_str("STORAGE_DIR", "storage")),
        chunk_size=_get_int("CHUNK_SIZE", 800),
        chunk_overlap=_get_int("CHUNK_OVERLAP", 120),
        top_k=_get_int("TOP_K", 5),
        retrieval_candidate_k=_get_int("RETRIEVAL_CANDIDATE_K", 20),
        similarity_cutoff=_get_float("SIMILARITY_CUTOFF", 0.25),
        rrf_k=_get_int("RRF_K", 60),
        vector_weight=_get_float("VECTOR_WEIGHT", 0.55),
        bm25_weight=_get_float("BM25_WEIGHT", 0.45),
        max_tokens=_get_int("MAX_TOKENS", 2048),
        temperature=_get_float("TEMPERATURE", 0.2),
        context_token_budget=_get_int("CONTEXT_TOKEN_BUDGET", 6000),
        max_history_turns=_get_int("MAX_HISTORY_TURNS", 10),
        log_level=_get_str("LOG_LEVEL", "INFO"),
    )
    if not overrides:
        return settings
    merged = {**settings.__dict__, **overrides}
    return Settings(**merged)


def validate_settings(settings: Settings) -> None:
    if settings.chunk_size <= 0:
        raise ValueError("CHUNK_SIZE must be greater than 0")
    if settings.chunk_overlap < 0:
        raise ValueError("CHUNK_OVERLAP must be greater than or equal to 0")
    if settings.chunk_size <= settings.chunk_overlap:
        raise ValueError("CHUNK_SIZE must be greater than CHUNK_OVERLAP")
    if settings.top_k < 1:
        raise ValueError("TOP_K must be at least 1")
    if settings.retrieval_candidate_k < settings.top_k:
        raise ValueError("RETRIEVAL_CANDIDATE_K must be greater than or equal to TOP_K")
    if not 0 <= settings.similarity_cutoff <= 1:
        raise ValueError("SIMILARITY_CUTOFF must be between 0 and 1")
    if not 0 <= settings.temperature <= 2:
        raise ValueError("TEMPERATURE must be between 0 and 2")
    if settings.max_history_turns < 1:
        raise ValueError("MAX_HISTORY_TURNS must be at least 1")


def validate_for_chat(settings: Settings) -> None:
    if not settings.deepseek_api_key:
        raise ValueError("DEEPSEEK_API_KEY is required for chat generation")


def ensure_directories(settings: Settings) -> None:
    for path in (settings.data_dir, settings.vectorstore_dir, settings.storage_dir):
        path.mkdir(parents=True, exist_ok=True)
        if not path.is_dir():
            raise ValueError(f"Path is not a directory: {path}")


def mask_secret(value: str, visible_prefix: int = 3, visible_suffix: int = 4) -> str:
    if not value:
        return ""
    if len(value) <= visible_prefix + visible_suffix:
        return "*" * len(value)
    return f"{value[:visible_prefix]}{'*' * 4}{value[-visible_suffix:]}"


def get_llm(settings: Settings) -> Any:
    """Create an OpenAI-compatible client for DeepSeek API.

    Uses the native openai SDK with base_url pointing to DeepSeek's endpoint.
    This avoids the model name validation that llama-index's wrapper enforces
    (which only accepts OpenAI model names).
    """
    validate_for_chat(settings)
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("openai package is not installed") from exc

    return OpenAI(
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
    )
