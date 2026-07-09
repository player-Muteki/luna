from __future__ import annotations

# DEPRECATED — use core.project (ProjectConfig, ProjectContext) instead.
import warnings as _warnings

_warnings.warn(
    "config.py (Settings, load_settings, etc.) is deprecated. "
    "Use core.project (ProjectConfig, ProjectContext) instead.",
    DeprecationWarning,
    stacklevel=2,
)

import os
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional during early bootstrap
    load_dotenv = None


def _load_env_file(dotenv_path: str | Path | None = None) -> None:
    """Load environment variables from a .env file.

    If *dotenv_path* is ``None`` (default), python-dotenv walks up from
    the current working directory looking for a ``.env`` file.  Pass an
    explicit path when the file is at a known location.
    """
    if load_dotenv is not None:
        load_dotenv(dotenv_path=dotenv_path, override=False)


def _get_str(name: str, default: str) -> str:
    value = os.getenv(name)
    # Treat empty string same as unset — avoids silent "" values for required config
    return default if value is None or value == "" else value


def _get_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value in (None, ""):
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(
            f"Environment variable {name}={value!r} is not a valid integer"
        ) from exc


def _get_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value in (None, ""):
        return default
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(
            f"Environment variable {name}={value!r} is not a valid float"
        ) from exc


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
    embedding_model_name: str
    embedding_base_url: str
    embedding_api_key: str
    parser_engine: str


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
        embedding_model_name=_get_str("EMBEDDING_MODEL_NAME", ""),
        embedding_base_url=_get_str("EMBEDDING_BASE_URL", "https://api.openai.com/v1"),
        embedding_api_key=_get_str("EMBEDDING_API_KEY", ""),
        parser_engine=_get_str("PARSER_ENGINE", "auto"),
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
    if settings.embedding_model_name and settings.embedding_base_url == settings.deepseek_base_url and "deepseek" in settings.embedding_base_url:
        warnings.warn("EMBEDDING_BASE_URL points to DeepSeek, which does not provide embedding endpoints. "
                       "Set EMBEDDING_BASE_URL to an OpenAI-compatible embedding provider (e.g. https://api.openai.com/v1) "
                       "or leave EMBEDDING_MODEL_NAME empty to use token-overlap fallback.")


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
    visible = visible_prefix + visible_suffix
    if len(value) <= visible:
        return "*" * len(value)
    return f"{value[:visible_prefix]}{'*' * min(4, len(value) - visible)}{value[-visible_suffix:]}"


def get_llm(settings: Settings) -> Any:
    """Create an OpenAI-compatible client for DeepSeek API."""
    validate_for_chat(settings)
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("openai package is not installed") from exc

    return OpenAI(
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
    )


class OpenAIEmbeddingModel:
    """OpenAI-compatible embedding model wrapper.

    Supports any provider that implements the OpenAI embeddings API shape
    (OpenAI, Ollama, Azure, etc.).
    """

    def __init__(self, model_name: str, base_url: str, api_key: str = "") -> None:
        from openai import OpenAI

        self.model_name = model_name
        self.client = OpenAI(api_key=api_key or "not-needed", base_url=base_url)

    def verify(self) -> bool:
        """Verify the embedding endpoint is reachable by sending a tiny test request.

        Returns True if the endpoint responds correctly, False otherwise.
        """
        try:
            self.get_text_embedding("test")
            return True
        except Exception:
            return False

    def get_text_embedding_batch(self, texts: list[str]) -> list[list[float]]:
        response = self.client.embeddings.create(input=texts, model=self.model_name)
        return [item.embedding for item in response.data]

    def get_text_embedding(self, text: str) -> list[float]:
        return self.get_text_embedding_batch([text])[0]

    def get_query_embedding(self, query: str) -> list[float]:
        return self.get_text_embedding(query)


def get_embedding_model(settings: Settings) -> Any | None:
    """Create an embedding model if configured, otherwise return None.

    When None is returned, vector retrieval falls back to token-overlap
    scoring.  To enable real semantic retrieval set:
      EMBEDDING_MODEL_NAME=text-embedding-3-small
      EMBEDDING_BASE_URL=https://api.openai.com/v1

    The endpoint is verified with a tiny test request so callers can detect
    misconfiguration (e.g. a DeepSeek URL that doesn't support embeddings)
    early rather than on the first query.
    """
    import logging as _log

    logger = _log.getLogger(__name__)
    if not settings.embedding_model_name:
        return None
    base_url = settings.embedding_base_url or "https://api.openai.com/v1"
    # Use dedicated embedding API key if configured, otherwise fall back to
    # the DeepSeek API key for backward compatibility.  If the embedding
    # provider is *not* DeepSeek, relying on the DeepSeek key means sending
    # the DeepSeek credential to a third party — users should set
    # EMBEDDING_API_KEY explicitly when using a non-DeepSeek provider.
    embedding_key = settings.embedding_api_key or settings.deepseek_api_key
    model = OpenAIEmbeddingModel(
        model_name=settings.embedding_model_name,
        base_url=base_url,
        api_key=embedding_key,
    )
    if not model.verify():
        logger.warning(
            "Embedding model %s at %s is not reachable. "
            "Vector retrieval will fall back to token-overlap scoring.",
            settings.embedding_model_name,
            base_url,
        )
        return None
    return model
