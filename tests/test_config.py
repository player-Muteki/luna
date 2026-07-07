from __future__ import annotations

from pathlib import Path

import pytest

from config import ensure_directories, load_settings, mask_secret, validate_settings


def test_load_settings_uses_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in (
        "DATA_DIR",
        "VECTORSTORE_DIR",
        "STORAGE_DIR",
        "CHUNK_SIZE",
        "CHUNK_OVERLAP",
        "TOP_K",
        "RETRIEVAL_CANDIDATE_K",
        "SIMILARITY_CUTOFF",
        "TEMPERATURE",
    ):
        monkeypatch.delenv(key, raising=False)

    settings = load_settings()

    assert settings.data_dir == Path("data")
    assert settings.vectorstore_dir == Path("vectorstore")
    assert settings.storage_dir == Path("storage")
    assert settings.chunk_size == 800
    assert settings.top_k == 5


def test_load_settings_supports_env_overrides(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "docs"))
    monkeypatch.setenv("VECTORSTORE_DIR", str(tmp_path / "vectors"))
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("CHUNK_SIZE", "256")
    monkeypatch.setenv("TOP_K", "7")

    settings = load_settings()

    assert settings.data_dir == tmp_path / "docs"
    assert settings.vectorstore_dir == tmp_path / "vectors"
    assert settings.storage_dir == tmp_path / "state"
    assert settings.chunk_size == 256
    assert settings.top_k == 7


def test_validate_settings_rejects_invalid_ranges() -> None:
    settings = load_settings(
        overrides={
            "chunk_size": 100,
            "chunk_overlap": 100,
        }
    )

    with pytest.raises(ValueError, match="CHUNK_SIZE"):
        validate_settings(settings)


def test_ensure_directories_and_mask_secret(tmp_path: Path) -> None:
    settings = load_settings(
        overrides={
            "data_dir": tmp_path / "data",
            "vectorstore_dir": tmp_path / "vectorstore",
            "storage_dir": tmp_path / "storage",
        }
    )

    ensure_directories(settings)

    assert settings.data_dir.is_dir()
    assert settings.vectorstore_dir.is_dir()
    assert settings.storage_dir.is_dir()
    assert mask_secret("sk-1234567890") == "sk-****7890"
