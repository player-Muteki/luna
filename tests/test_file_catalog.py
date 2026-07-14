"""
FileCatalog 测试 — 文件发现的单一真相来源。

覆盖：
  - browse() 返回文件树（含目录 + 索引状态）
  - ingest_candidates() 返回可索引文件
  - 隐藏文件排除
  - exclude_patterns
  - extension 过滤
  - max file size（仅 browse）
  - 子目录浏览
  - manifest 索引状态标注
  - browse 和 ingest 规则一致
"""

from __future__ import annotations

from core.file_catalog import FileCatalog
from core.ingest import DocumentManifest
from core.project import ProjectConfig


# ── 辅助 ──────────────────────────────────────────────────────────


def _make_catalog(tmp_path, **config_overrides) -> FileCatalog:
    """创建一个使用默认配置的 FileCatalog。"""
    co_dir = tmp_path / ".luna"
    co_dir.mkdir(parents=True, exist_ok=True)
    (co_dir / "vectordb").mkdir(parents=True, exist_ok=True)

    config = ProjectConfig.load(co_dir / "config.toml")
    config.chunk_size = 200
    config.chunk_overlap = 20
    for key, value in config_overrides.items():
        if hasattr(config, key):
            setattr(config, key, value)

    return FileCatalog(
        root=tmp_path,
        exclude_patterns=config.exclude_patterns,
        supported_extensions=config.supported_extensions,
        max_file_size_mb=config.max_file_size_mb,
    )


# ═══════════════════════════════════════════════════════════════════
#  browse()
# ═══════════════════════════════════════════════════════════════════


class TestBrowse:
    def test_returns_all_supported_files(self, tmp_path) -> None:
        (tmp_path / "readme.md").write_text("# Hello", encoding="utf-8")
        (tmp_path / "main.py").write_text("print('hello')", encoding="utf-8")

        catalog = _make_catalog(tmp_path)
        files = catalog.browse()

        paths = [f["path"] for f in files if not f["is_dir"]]
        assert "readme.md" in paths
        assert "main.py" in paths

    def test_returns_directories(self, tmp_path) -> None:
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "lib.py").write_text("x=1", encoding="utf-8")

        catalog = _make_catalog(tmp_path)
        files = catalog.browse()

        dirs = [f for f in files if f["is_dir"]]
        files_only = [f for f in files if not f["is_dir"]]
        assert "src" in {d["path"] for d in dirs}
        assert "src/lib.py" in {f["path"] for f in files_only}

    def test_subdir_scope(self, tmp_path) -> None:
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.py").write_text("x", encoding="utf-8")
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "guide.md").write_text("# Guide", encoding="utf-8")

        catalog = _make_catalog(tmp_path)
        files = catalog.browse(subdir="docs")

        paths = [f["path"] for f in files if not f["is_dir"]]
        assert "docs/guide.md" in paths

    def test_dirs_first_then_sorted(self, tmp_path) -> None:
        (tmp_path / "zzz").mkdir()
        (tmp_path / "aaa").mkdir()
        (tmp_path / "aaa" / "file.md").write_text("x", encoding="utf-8")
        (tmp_path / "bbb.md").write_text("x", encoding="utf-8")

        catalog = _make_catalog(tmp_path)
        files = catalog.browse()

        order = [f["path"] for f in files]
        assert order == ["aaa", "zzz", "aaa/file.md", "bbb.md"]

    def test_nonexistent_subdir_returns_empty(self, tmp_path) -> None:
        catalog = _make_catalog(tmp_path)
        assert catalog.browse(subdir="nonexistent") == []


# ═══════════════════════════════════════════════════════════════════
#  ingest_candidates()
# ═══════════════════════════════════════════════════════════════════


class TestIngestCandidates:
    def test_returns_only_files(self, tmp_path) -> None:
        (tmp_path / "src").mkdir()
        (tmp_path / "main.py").write_text("x=1", encoding="utf-8")

        catalog = _make_catalog(tmp_path)
        candidates = catalog.ingest_candidates()

        assert all(p.is_file() for p in candidates)
        assert len(candidates) == 1
        assert candidates[0].name == "main.py"

    def test_custom_root_dir(self, tmp_path) -> None:
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "inner.md").write_text("x", encoding="utf-8")
        (tmp_path / "outer.md").write_text("x", encoding="utf-8")

        catalog = _make_catalog(tmp_path)
        candidates = catalog.ingest_candidates(root_dir=tmp_path / "sub")

        assert len(candidates) == 1
        assert candidates[0].name == "inner.md"

    def test_empty_dir_returns_empty(self, tmp_path) -> None:
        catalog = _make_catalog(tmp_path)
        assert catalog.ingest_candidates() == []

    def test_nonexistent_root_dir_returns_empty(self, tmp_path) -> None:
        catalog = _make_catalog(tmp_path)
        assert catalog.ingest_candidates(root_dir="/nonexistent") == []


# ═══════════════════════════════════════════════════════════════════
#  排除规则
# ═══════════════════════════════════════════════════════════════════


class TestExclusions:
    def test_hidden_files_excluded(self, tmp_path) -> None:
        (tmp_path / "visible.md").write_text("x", encoding="utf-8")
        (tmp_path / ".hidden.md").write_text("x", encoding="utf-8")

        catalog = _make_catalog(tmp_path)
        browse_files = catalog.browse()
        ingest_files = catalog.ingest_candidates()

        browse_paths = [f["path"] for f in browse_files if not f["is_dir"]]
        assert "visible.md" in browse_paths
        assert ".hidden.md" not in browse_paths
        assert all(p.name != ".hidden.md" for p in ingest_files)

    def test_hidden_dirs_excluded(self, tmp_path) -> None:
        (tmp_path / ".git").mkdir()
        (tmp_path / ".git" / "config").write_text("x", encoding="utf-8")
        (tmp_path / "readme.md").write_text("x", encoding="utf-8")

        catalog = _make_catalog(tmp_path)
        browse_files = catalog.browse()
        ingest_files = catalog.ingest_candidates()

        assert "readme.md" in {f["path"] for f in browse_files if not f["is_dir"]}
        assert all(".git" not in p.parts for p in ingest_files)

    def test_luna_excluded(self, tmp_path) -> None:
        """.luna 目录及其内容不应出现在扫描结果中。"""
        (tmp_path / ".luna" / "config.toml").parent.mkdir(parents=True)
        (tmp_path / ".luna" / "config.toml").write_text(
            "[project]\nmodel = 'test'\n", encoding="utf-8"
        )
        (tmp_path / "readme.md").write_text("x", encoding="utf-8")

        config = ProjectConfig.load(tmp_path / ".luna" / "config.toml")
        catalog = FileCatalog(
            root=tmp_path,
            exclude_patterns=config.exclude_patterns,
            supported_extensions=config.supported_extensions,
            max_file_size_mb=config.max_file_size_mb,
        )
        browse_files = catalog.browse()
        ingest_files = catalog.ingest_candidates()

        assert "readme.md" in {f["path"] for f in browse_files if not f["is_dir"]}
        assert all(".luna" not in p.parts for p in ingest_files)

    def test_unsupported_extension_excluded(self, tmp_path) -> None:
        (tmp_path / "readme.md").write_text("x", encoding="utf-8")
        (tmp_path / "binary.bin").write_text("x", encoding="utf-8")

        catalog = _make_catalog(tmp_path)
        browse_files = catalog.browse()
        ingest_files = catalog.ingest_candidates()

        browse_paths = [f["path"] for f in browse_files if not f["is_dir"]]
        assert "readme.md" in browse_paths
        assert "binary.bin" not in browse_paths
        assert all(p.suffix != ".bin" for p in ingest_files)

    def test_max_file_size_excluded(self, tmp_path) -> None:
        (tmp_path / "small.md").write_text("x", encoding="utf-8")
        (tmp_path / "large.md").write_text("x" * (2 * 1024 * 1024), encoding="utf-8")

        catalog = _make_catalog(tmp_path, max_file_size_mb=1)
        browse_files = catalog.browse()

        browse_paths = [f["path"] for f in browse_files if not f["is_dir"]]
        assert "small.md" in browse_paths
        assert "large.md" not in browse_paths

    def test_ingest_ignores_max_file_size(self, tmp_path) -> None:
        """索引引擎不检查文件大小（即使超大文件也可以索引）。"""
        (tmp_path / "large.md").write_text("x" * (20 * 1024 * 1024), encoding="utf-8")

        catalog = _make_catalog(tmp_path, max_file_size_mb=1)
        ingest_files = catalog.ingest_candidates()

        assert any(p.name == "large.md" for p in ingest_files)


# ═══════════════════════════════════════════════════════════════════
#  索引状态标注
# ═══════════════════════════════════════════════════════════════════


class TestIndexedStatus:
    def test_browse_marks_indexed_files(self, tmp_path) -> None:
        co_dir = tmp_path / ".luna"
        (co_dir / "vectordb").mkdir(parents=True, exist_ok=True)

        (tmp_path / "indexed.md").write_text("# Indexed", encoding="utf-8")
        (tmp_path / "pending.md").write_text("# Pending", encoding="utf-8")

        # 创建 manifest 并标记一个文件已索引
        manifest_path = co_dir / "vectordb" / "manifest.json"
        manifest = DocumentManifest(manifest_path)
        manifest.upsert_document({
            "document_id": "doc_indexed",
            "source_path": "indexed.md",
            "file_name": "indexed.md",
            "status": "indexed",
            "content_hash": "abc",
            "chunk_count": 2,
        })

        catalog = FileCatalog(
            root=tmp_path,
            exclude_patterns=[],
            supported_extensions=[".md"],
            max_file_size_mb=20,
            manifest=manifest,
        )
        browse_files = catalog.browse()

        indexed = {f["path"] for f in browse_files if not f["is_dir"] and f["is_indexed"]}
        pending = {f["path"] for f in browse_files if not f["is_dir"] and not f["is_indexed"]}

        assert "indexed.md" in indexed
        assert "pending.md" in pending

    def test_browse_no_manifest_no_crash(self, tmp_path) -> None:
        """没有 manifest 时不标注索引状态，也不崩溃。"""
        (tmp_path / "readme.md").write_text("# Hello", encoding="utf-8")

        catalog = _make_catalog(tmp_path)
        files = catalog.browse()

        for f in files:
            if not f["is_dir"]:
                assert not f["is_indexed"]
                assert f["document_id"] == ""


# ═══════════════════════════════════════════════════════════════════
#  规则一致性
# ═══════════════════════════════════════════════════════════════════


class TestConsistency:
    def test_browse_and_ingest_agree_on_visible_files(self, tmp_path) -> None:
        """browse 和 ingest 对同一文件的包含/排除判断一致。"""
        (tmp_path / "visible.md").write_text("x", encoding="utf-8")
        hidden = tmp_path / ".hidden"
        hidden.mkdir()
        (hidden / "secret.md").write_text("x", encoding="utf-8")
        (tmp_path / "readme.md").write_text("x", encoding="utf-8")

        catalog = _make_catalog(tmp_path)
        browse = {f["path"] for f in catalog.browse() if not f["is_dir"]}
        ingest = {str(p.relative_to(tmp_path)) for p in catalog.ingest_candidates()}

        assert browse == ingest, (
            f"browse and ingest disagree on visible files\n"
            f"browse: {sorted(browse)}\n"
            f"ingest: {sorted(ingest)}"
        )
