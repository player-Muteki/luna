"""
FileCatalog — 文件发现的单一真相来源。

集中管理工作目录的包含 / 排除规则（exclude patterns、hidden 文件、
supported extensions、max file size），对外提供两个视图：

* ``browse()`` → 前端文件树（含索引状态）
* ``ingest_candidates()`` → 索引引擎候选文件

浏览和索引不再各自实现扫描逻辑。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


class FileCatalog:
    """单一真相来源：工作目录中哪些文件可视 / 可索引。"""

    def __init__(
        self,
        root: Path,
        exclude_patterns: list[str],
        supported_extensions: list[str],
        max_file_size_mb: int,
        manifest: Any | None = None,
    ):
        self.root = root.resolve()
        self.exclude_set = set(exclude_patterns)
        self.ext_set = set(supported_extensions)
        self.max_bytes = max_file_size_mb * 1024 * 1024
        self.manifest = manifest  # Optional DocumentManifest, used for indexed status in browse()

    # ── 公开接口 ──────────────────────────────────────────────────

    def browse(self, subdir: str | None = None) -> list[dict[str, Any]]:
        """前端文件树：文件和目录（含索引状态）。

        返回形状与 ProjectContext.scan_files() 一致，方便无缝替换。
        """
        scan_root = (self.root / subdir) if subdir else self.root
        if not scan_root.exists() or not scan_root.is_dir():
            return []

        indexed_map = self._build_indexed_map()

        files: list[dict[str, Any]] = []
        for path in scan_root.rglob("*"):
            if not self._should_include(path):
                continue

            rel = path.relative_to(self.root)

            if path.is_dir():
                files.append({
                    "path": str(rel),
                    "name": path.name,
                    "ext": "",
                    "size": 0,
                    "mtime": path.stat().st_mtime,
                    "is_dir": True,
                    "is_indexed": False,
                    "document_id": "",
                })
            elif path.is_file():
                if path.suffix.lower() not in self.ext_set:
                    continue
                if path.stat().st_size > self.max_bytes:
                    continue

                sp = str(rel)
                doc_id = indexed_map.get(sp, "")
                files.append({
                    "path": sp,
                    "name": path.name,
                    "ext": path.suffix.lower(),
                    "size": path.stat().st_size,
                    "mtime": path.stat().st_mtime,
                    "is_dir": False,
                    "is_indexed": bool(doc_id),
                    "document_id": doc_id,
                })

        files.sort(key=lambda f: (not f["is_dir"], f["path"]))
        return files

    def ingest_candidates(self, root_dir: str | Path | None = None) -> list[Path]:
        """索引引擎候选文件：仅返回支持的可索引文件，不含目录。

        返回形状与 IngestionEngine.scan_files() 一致。
        """
        scan_root = Path(root_dir).resolve() if root_dir else self.root
        if not scan_root.exists() or not scan_root.is_dir():
            return []

        candidates: list[Path] = []
        for path in scan_root.rglob("*"):
            if not path.is_file():
                continue
            if not self._should_include(path):
                continue
            if path.suffix.lower() not in self.ext_set:
                continue
            # 索引引擎不检查文件大小（不截断，所有内容都应可索引）
            candidates.append(path)

        return sorted(candidates)

    # ── 内部过滤 ──────────────────────────────────────────────────

    def _should_include(self, path: Path) -> bool:
        """核心过滤：路径是否应出现在 catalog 中。

        规则（优先级从高到低）：
        1. 始终排除 .co-thinker 工作目录
        2. 是否匹配 exclude_patterns 中的任意一项
        3. 是否在隐藏目录中（以 '.' 开头）
        """
        if ".co-thinker" in path.parts:
            return False

        if any(part in self.exclude_set for part in path.parts):
            return False

        if any(part.startswith(".") for part in path.parts):
            return False

        return True

    # ── 内部工具 ──────────────────────────────────────────────────

    def _build_indexed_map(self) -> dict[str, str]:
        """从 manifest 构建 {source_path → document_id} 映射。"""
        if self.manifest is None:
            return {}
        try:
            indexed_map: dict[str, str] = {}
            for doc in self.manifest.list_documents():
                if doc.get("status") == "indexed":
                    indexed_map[doc["source_path"]] = doc["document_id"]
            return indexed_map
        except Exception:
            return {}
