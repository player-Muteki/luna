"""
ProjectContext — Co-Thinker 与工作目录的绑定桩。

每个进程绑定到一个 CWD，通过它访问所有资源。

全局配置 (~/.co-thinkerc)：
  [auth]
  api_key = "sk-..."

  [model]
  name = "deepseek-chat"
  base_url = "https://api.deepseek.com"
"""

from __future__ import annotations

import json
import logging
import os
import re as _re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

GLOBAL_CONFIG_PATH = Path.home() / ".co-thinkerc"

logger = logging.getLogger(__name__)

# ── 默认配置值 ────────────────────────────────────────────────────────


def _default_exclude_patterns() -> list[str]:
    return [".git", "__pycache__", "node_modules", ".venv", ".co-thinker", ".DS_Store"]


def _default_supported_extensions() -> list[str]:
    return [
        ".c", ".cpp", ".cs", ".go", ".h", ".hpp", ".java", ".js", ".jsx",
        ".kt", ".kts", ".lua", ".php", ".pl", ".pm", ".py", ".rb", ".rs",
        ".scala", ".swift", ".ts", ".tsx",
        ".md", ".mdx", ".rst", ".tex", ".sty", ".cls", ".bib", ".bst",
        ".html", ".htm", ".txt",
        ".json", ".yaml", ".yml", ".toml", ".xml", ".ini", ".cfg", ".conf", ".env",
        ".csv", ".sql", ".log",
        ".sh", ".bash", ".zsh", ".m", ".mm", ".r", ".R",
        ".tf", ".cmake", ".gradle",
        ".pdf", ".docx", ".pptx",
    ]


def _load_global_config() -> dict[str, Any]:
    """读取 ~/.co-thinkerc 全局配置（不存在则返回空字典）。"""
    path = GLOBAL_CONFIG_PATH
    if not path.exists():
        return {}
    raw = path.read_text(encoding="utf-8")
    if not raw.strip():
        return {}
    try:
        import tomli
    except ImportError:
        try:
            import tomllib as tomli  # type: ignore[no-redef]
        except ImportError:
            return {}
    try:
        return tomli.loads(raw)
    except Exception:
        logger.warning("Failed to parse %s", path)
        return {}


def _global_auth_api_key() -> str:
    """从 ~/.co-thinkerc 读取 API Key。"""
    cfg = _load_global_config()
    return cfg.get("auth", {}).get("api_key", "")


def _global_model_name() -> str:
    cfg = _load_global_config()
    return cfg.get("model", {}).get("name", "")


def _global_model_base_url() -> str:
    cfg = _load_global_config()
    return cfg.get("model", {}).get("base_url", "")


@dataclass
class ProjectConfig:
    """从 .co-thinker/config.toml 读取的配置"""
    model: str = "deepseek-chat"
    base_url: str = "https://api.deepseek.com"
    embedding_model: str = ""
    embedding_base_url: str = "https://api.openai.com/v1"
    embedding_api_key: str = ""
    chunk_size: int = 800
    chunk_overlap: int = 120
    top_k: int = 5
    retrieval_candidate_k: int = 20
    similarity_cutoff: float = 0.25
    rrf_k: int = 60
    vector_weight: float = 0.55
    bm25_weight: float = 0.45
    max_tokens: int = 2048
    temperature: float = 0.2
    context_token_budget: int = 6000
    max_history_turns: int = 10
    log_level: str = "INFO"
    parser_engine: str = "auto"
    exclude_patterns: list[str] = field(default_factory=_default_exclude_patterns)
    max_file_size_mb: int = 20
    supported_extensions: list[str] = field(default_factory=_default_supported_extensions)

    @classmethod
    def load(cls, path: Path) -> "ProjectConfig":
        """从项目 .co-thinker/.config.toml 加载配置，合并全局 ~/.co-thinkerc。

        优先级（后者覆盖前者）：
          1. 默认值
          2. 全局 ~/.co-thinkerc 的 [project] 段
          3. 项目 .co-thinker/.config.toml 的 [project] 段
        """
        known_keys = set(cls.__dataclass_fields__.keys())

        # 从全局配置加载 [project] 段
        global_cfg = _load_global_config()
        global_project = global_cfg.get("project", {})

        # 从项目配置加载 [project] 段
        local_project: dict[str, Any] = {}
        if path.exists():
            raw = path.read_text(encoding="utf-8")
            if raw.strip():
                try:
                    import tomli
                except ImportError:
                    try:
                        import tomllib as tomli  # type: ignore[no-redef]
                    except ImportError:
                        raise RuntimeError("需要 tomli 或 Python 3.11+ 来读取 TOML 配置")
                data = tomli.loads(raw)
                if "project" in data:
                    for key, value in data["project"].items():
                        if key in known_keys:
                            local_project[key] = value
                        else:
                            logger.warning("Unknown config key [project].%s, ignoring", key)

        # 合并：默认值 ← 全局 ← 本地项目
        config_data = {}
        for key in known_keys:
            if key in local_project:
                config_data[key] = local_project[key]
            elif key in global_project:
                config_data[key] = global_project[key]
            # 其余保持默认值

        return cls(**config_data)

    def merge_global_overrides(self) -> None:
        """用全局配置中 [project] 段覆盖当前实例的字段（仅当字段值为默认值且全局有值）。"""
        global_cfg = _load_global_config()
        global_project = global_cfg.get("project", {})
        for key, value in global_project.items():
            if hasattr(self, key) and getattr(self, key) == self.__dataclass_fields__[key].default:
                setattr(self, key, value)

    def save(self, path: Path) -> None:
        """将配置保存为 TOML 文件。"""
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            import tomli_w
        except ImportError:
            raise RuntimeError("需要 tomli-w 来写入 TOML 配置")

        config_dict = {}
        for field_name in self.__dataclass_fields__:
            value = getattr(self, field_name)
            config_dict[field_name] = value

        import tomli_w as _tomli_w
        content = "# Co-Thinker Project Configuration\n" + _tomli_w.dumps({"project": config_dict})
        path.write_text(content, encoding="utf-8")


class ProjectContext:
    """绑定到一个工作目录，持有 RAG 引擎的所有状态。"""

    def __init__(self, root: Path):
        self.root = root.resolve()
        self.co_dir = self.root / ".co-thinker"
        self.config_path = self.co_dir / "config.toml"
        self.env_path = self.co_dir / ".env"
        self.vectordb_dir = self.co_dir / "vectordb"
        self.chunks_path = self.vectordb_dir / "chunks.json"
        self.manifest_path = self.vectordb_dir / "manifest.json"
        self.sessions_path = self.co_dir / "sessions.jsonl"

        self.config = ProjectConfig.load(self.config_path)

        # 各种引擎（由外部工厂组装后设置）
        self.vectorstore: Any | None = None
        self.manifest: Any | None = None
        self.embedding_model: Any | None = None
        self.llm: Any | None = None
        self.generator: Any | None = None
        self.ingest_engine: Any | None = None
        self.retriever: Any | None = None
        self.chat_engine: Any | None = None

    @staticmethod
    def load(explicit: str | None = None) -> "ProjectContext":
        """
        解析项目根目录并创建 ProjectContext。
        优先级：
        1. explicit（--dir 参数）
        2. CWD
        """
        if explicit:
            root = Path(explicit).resolve()
        else:
            root = Path.cwd().resolve()

        ctx = ProjectContext(root)
        ctx._ensure_co_dir()
        return ctx

    def _ensure_co_dir(self) -> None:
        """确保 .co-thinker/ 及子目录存在。"""
        self.co_dir.mkdir(parents=True, exist_ok=True)
        self.vectordb_dir.mkdir(parents=True, exist_ok=True)

    def setup_engines(self) -> None:
        """组装所有 RAG 引擎组件（ingest, retriever, chat, generator）。

        调用前需先设置好 llm 和 embedding_model。
        """
        from core.ingest import IngestionEngine, VectorStore
        from core.retriever import HybridRetriever
        from core.generator import RAGGenerator
        from core.chat_engine import ChatEngine

        vectorstore = VectorStore(self.chunks_path)
        self.vectorstore = vectorstore

        self.ingest_engine = IngestionEngine(
            config=self.config,
            root=self.root,
            embedding_model=self.embedding_model,
            vector_store=vectorstore,
        )
        self.manifest = self.ingest_engine.manifest

        self.retriever = HybridRetriever(
            config=self.config,
            vector_store=vectorstore,
            embedding_model=self.embedding_model,
        )

        self.chat_engine = ChatEngine(
            storage_path=self.sessions_path,
            max_history_turns=self.config.max_history_turns,
        )

        self.generator = RAGGenerator(config=self.config, llm=self.llm)

    def save_config(self) -> None:
        """持久化当前配置。"""
        self.config.save(self.config_path)

    # ── 文件扫描 ─────────────────────────────────────────────────────

    def scan_files(self, subdir: str | None = None) -> list[dict[str, Any]]:
        """扫描工作目录，返回文件列表（含索引状态），供前端勾选。

        由 ``FileCatalog.browse()`` 实现。
        """
        from core.file_catalog import FileCatalog

        catalog = FileCatalog(
            root=self.root,
            exclude_patterns=self.config.exclude_patterns,
            supported_extensions=self.config.supported_extensions,
            max_file_size_mb=self.config.max_file_size_mb,
            manifest=self.manifest,
        )
        return catalog.browse(subdir=subdir)

    def get_project_info(self) -> dict[str, Any]:
        """返回项目信息，供前端展示。"""
        stats = {}
        if self.manifest:
            docs = self.manifest.list_documents()
            indexed = [d for d in docs if d.get("status") == "indexed"]
            stats = {
                "document_count": len(docs),
                "indexed_count": len(indexed),
                "chunk_count": self.vectorstore.count_chunks() if self.vectorstore else 0,
            }

        return {
            "root": str(self.root),
            "name": self.root.name,
            "config": {
                "model": self.config.model,
                "chunk_size": self.config.chunk_size,
                "top_k": self.config.top_k,
                "max_history_turns": self.config.max_history_turns,
            },
            "stats": stats,
        }


# ── 辅助函数 ──────────────────────────────────────────────────────────


def get_api_key(ctx: ProjectContext) -> str:
    """获取 API Key，优先级：进程环境变量 > ~/.co-thinkerc > .co-thinker/.env（兼容旧版）。"""
    key = os.getenv("DEEPSEEK_API_KEY", "")
    if not key:
        key = _global_auth_api_key()
    if not key:
        if ctx.env_path.exists():
            m = _re.search(r'^DEEPSEEK_API_KEY=(.+)$', ctx.env_path.read_text(encoding="utf-8"), _re.MULTILINE)
            if m:
                key = m.group(1).strip().strip('"\'')
    return key


def get_llm(ctx: ProjectContext) -> Any:
    """创建 OpenAI 兼容客户端。base_url 优先级：全局 ~/.co-thinkerc > 项目配置 > 默认值。"""
    api_key = get_api_key(ctx)
    if not api_key:
        raise ValueError("DEEPSEEK_API_KEY 未设置")
    base_url = _global_model_base_url() or ctx.config.base_url
    try:
        from openai import OpenAI
    except ImportError:
        raise RuntimeError("openai 包未安装")
    return OpenAI(api_key=api_key, base_url=base_url)


def get_embedding_model(ctx: ProjectContext) -> Any | None:
    """创建 embedding 模型（如果配置了）。"""
    if not ctx.config.embedding_model:
        return None
    try:
        from openai import OpenAI
    except ImportError:
        return None
    api_key = ctx.config.embedding_api_key or get_api_key(ctx)
    if not ctx.config.embedding_api_key and ctx.config.embedding_base_url != ctx.config.base_url:
        logger.warning(
            "EMBEDDING_BASE_URL differs from the LLM base URL, but EMBEDDING_API_KEY is not set. "
            "Falling back to the LLM API key — if the embedding provider is not DeepSeek, "
            "set EMBEDDING_API_KEY explicitly to avoid sending credentials to a third party."
        )
    client = OpenAI(api_key=api_key or "not-needed", base_url=ctx.config.embedding_base_url)

    class EmbeddingModel:
        def __init__(self, model_name: str, client: Any):
            self.model_name = model_name
            self.client = client

        def get_text_embedding(self, text: str) -> list[float]:
            return self.get_text_embedding_batch([text])[0]

        def get_query_embedding(self, query: str) -> list[float]:
            return self.get_text_embedding(query)

        def get_text_embedding_batch(self, texts: list[str]) -> list[list[float]]:
            response = self.client.embeddings.create(input=texts, model=self.model_name)
            return [item.embedding for item in response.data]

    return EmbeddingModel(ctx.config.embedding_model, client)
