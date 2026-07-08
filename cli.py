"""
Co-Thinker CLI — 工作目录绑定型 RAG 知识库系统。

Usage:
    co-thinker init             在当前目录创建 .co-thinker/ + 默认配置
    co-thinker start            启动 Web UI（FastAPI + Next.js）
    co-thinker start --port 8080
    co-thinker run "问题"       非交互式一键问答
    co-thinker scan             扫描工作目录，显示文件索引状态
    co-thinker version          显示版本
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import time
from pathlib import Path

import typer

from __version__ import __version__

BANNER = r"""
   ____          _   _   _           _
  / ___|___   __| | | |_| |__  _ __ | | _____ _ __
 | |   / _ \ / _` | | __| '_ \| '_ \| |/ / _ \ '__|
 | |__| (_) | (_| | | |_| | | | | | |   <  __/ |
  \____\___/ \__,_|  \__|_| |_|_| |_|_|\_\___|_|

  基于 RAG 的工作目录知识库  v{version}
"""

app = typer.Typer(
    name="co-thinker",
    help="基于 RAG 的工作目录知识库系统",
    no_args_is_help=True,
    add_completion=False,
)

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def _banner(version: str) -> str:
    return BANNER.format(version=version)


def _setup_project_context() -> object:
    """Create and wire up a ProjectContext with all engines."""
    from core.project import ProjectContext, get_api_key, get_llm, get_embedding_model

    ctx = ProjectContext.load()

    # API key
    api_key = ""
    try:
        api_key = get_api_key(ctx)
    except Exception:
        pass

    if api_key:
        try:
            ctx.llm = get_llm(ctx)
        except Exception:
            pass

    ctx.embedding_model = get_embedding_model(ctx)
    ctx.setup_engines()

    return ctx


# ═══════════════════════════════════════════════════════════════════════
#  Commands
# ═══════════════════════════════════════════════════════════════════════


@app.command()
def init(
    dir: Path = typer.Argument(
        ".",
        help="工作目录（默认当前目录）",
    ),
):
    """在当前目录初始化 .co-thinker/ 配置目录"""
    cwd = dir.resolve()
    cwd.mkdir(parents=True, exist_ok=True)

    print(_banner(__version__))
    typer.echo(f"[DIR] 工作目录: {cwd}")
    typer.echo("")

    co_dir = cwd / ".co-thinker"
    vectordb_dir = co_dir / "vectordb"
    config_path = co_dir / ".config.toml"

    co_dir.mkdir(parents=True, exist_ok=True)
    vectordb_dir.mkdir(parents=True, exist_ok=True)
    typer.echo(f"[OK] 已创建: {co_dir}/")

    # 创建默认项目配置
    if not config_path.exists():
        try:
            import tomli_w
        except ImportError:
            os.system(f"{sys.executable} -m pip install tomli-w")
            try:
                import tomli_w  # type: ignore[import-untyped]
            except ImportError:
                typer.echo("[WARN] 无法安装 tomli-w，跳过 config.toml 创建")
                config_path = None

        if config_path:
            _write_default_config(config_path)
            typer.echo(f"[OK] 已创建: {config_path}")
    else:
        typer.echo(f"[OK] 已存在: {config_path}")

    # 检查全局配置 ~/.co-thinkerc
    from core.project import GLOBAL_CONFIG_PATH, _load_global_config

    if not GLOBAL_CONFIG_PATH.exists():
        typer.echo("")
        typer.echo("[WARN] 未检测到全局配置 ~/.co-thinkerc")
        if typer.confirm("  是否现在创建？（需要填入 DeepSeek API Key）", default=True):
            api_key = typer.prompt("  DeepSeek API Key", hide_input=True)
            if api_key:
                _write_global_config(api_key)
                typer.echo(f"  [OK] 已创建: {GLOBAL_CONFIG_PATH}")
            else:
                typer.echo("  [SKIP] 跳过，可稍后手动创建")
        else:
            typer.echo("  [SKIP] 跳过，可稍后手动创建")
    else:
        typer.echo(f"[OK] 已存在: {GLOBAL_CONFIG_PATH}")

    typer.echo("")
    typer.echo("[DONE] 初始化完成！运行 co-thinker start 启动 Web 界面。")


@app.command()
def start(
    port: int = typer.Option(3001, "--port", "-p", help="Web UI 端口号"),
    api_port: int = typer.Option(8765, "--api-port", help="API 服务端口号"),
    open_browser: bool = typer.Option(True, "--open/--no-open", help="启动后自动打开浏览器"),
):
    """启动 Co-Thinker Web 界面（FastAPI + Next.js）"""
    cwd = Path.cwd().resolve()
    print(_banner(__version__))
    typer.echo(f"[DIR] 工作目录: {cwd}")

    # 检查 .co-thinker 是否存在
    co_dir = cwd / ".co-thinker"
    if not co_dir.exists():
        typer.echo("[WARN] 未检测到 .co-thinker/ 目录。请先运行 co-thinker init。")
        typer.echo("")
        if not typer.confirm("是否现在就初始化？", default=True):
            raise typer.Exit(1)
        init(dir=cwd)
        typer.echo("")

    os.environ.setdefault("CO_THINKER_ROOT", str(cwd))

    web_dir = Path(__file__).resolve().parent / "web"

    # 检查 Next.js 前端是否存在
    if web_dir.exists():
        typer.echo(f"[WEB] 启动 Next.js 前端 (port {port})...")
        _start_full_stack(web_dir, port, api_port, cwd, open_browser)
    else:
        typer.echo(f"[WEB] 前端尚未构建，仅启动 API 服务 (port {api_port})")
        _start_api_only(api_port, cwd)


@app.command()
def run(
    query: str = typer.Argument(
        ...,
        help="要提问的问题",
    ),
    dir: str = typer.Option(None, "--dir", help="项目目录（默认当前目录）"),
):
    """非交互式一键问答（CLI 模式）"""
    print(_banner(__version__))
    typer.echo(f"[Q] {query}")
    typer.echo("")

    ctx = _setup_project_context()

    # 确保有索引数据
    if not ctx.vectorstore or ctx.vectorstore.count_chunks() == 0:
        typer.echo("[INFO] 索引为空，正在扫描并索引文件...")
        files = ctx.ingest_engine.scan_files()
        if files:
            summary = ctx.ingest_engine.add_files(files)
            typer.echo(f"[OK] 已索引 {summary.indexed_files} 个文件，共 {summary.total_chunks} 个片段")
        else:
            typer.echo("[WARN] 工作目录中未找到可索引的文件")
            raise typer.Exit(0)

    # 检索
    results = ctx.retriever.retrieve(query)
    if not results.results:
        typer.echo("[INFO] 知识库中未找到相关信息")
        raise typer.Exit(0)

    # 生成
    generation = ctx.generator.generate(query, results)
    typer.echo(generation.answer)
    typer.echo("")

    # 显示引用来源
    if generation.references:
        typer.echo("── 引用来源 ──")
        for i, ref in enumerate(generation.references[:5], 1):
            typer.echo(f"  [{i}] {ref.source_path} (score: {ref.score:.3f})")


@app.command()
def scan(
    dir: str = typer.Option(None, "--dir", help="项目目录（默认当前目录）"),
):
    """扫描工作目录，显示文件索引状态"""
    from core.project import ProjectContext

    ctx = ProjectContext.load(dir)
    files = ctx.scan_files()

    files_only = [f for f in files if not f["is_dir"]]
    dirs_only = [f for f in files if f["is_dir"]]

    indexed = sum(1 for f in files_only if f["is_indexed"])
    total = len(files_only)

    typer.echo(f"工作目录: {ctx.root}")
    typer.echo(f"文件总数: {total}, 已索引: {indexed}")
    typer.echo("")

    # 显示文件树
    for d in dirs_only:
        typer.echo(f"  📁 {d['path']}/")
    for f in files_only:
        status = "☑" if f["is_indexed"] else "☐"
        typer.echo(f"  {status} {f['path']} ({_fmt_size(f['size'])})")


@app.command()
def version():
    """显示版本与系统信息"""
    print(_banner(__version__))

    installed_path = Path(__file__).resolve().parent
    in_site_packages = "site-packages" in installed_path.parts

    typer.echo(f"版本:      {__version__}")
    typer.echo(f"安装方式:  {'pip 安装' if in_site_packages else '源码运行'}")
    typer.echo(f"包路径:    {installed_path}")
    typer.echo(f"Python:    {sys.version.split()[0]}")


# ═══════════════════════════════════════════════════════════════════════
#  Internal helpers
# ═══════════════════════════════════════════════════════════════════════


def _write_default_config(path: Path) -> None:
    """写入默认 config.toml。"""
    import tomli_w as tw

    config = {
        "project": {
            "model": "deepseek-chat",
            "base_url": "https://api.deepseek.com",
            "chunk_size": 800,
            "chunk_overlap": 120,
            "top_k": 5,
            "retrieval_candidate_k": 20,
            "similarity_cutoff": 0.25,
            "rrf_k": 60,
            "vector_weight": 0.55,
            "bm25_weight": 0.45,
            "max_tokens": 2048,
            "temperature": 0.2,
            "context_token_budget": 6000,
            "max_history_turns": 10,
            "log_level": "INFO",
            "parser_engine": "auto",
            "max_file_size_mb": 20,
        }
    }
    path.write_text("# Co-Thinker Project Configuration\n" + tw.dumps(config), encoding="utf-8")


def _write_global_config(api_key: str) -> None:
    """创建 ~/.co-thinkerc 全局配置文件。"""
    import tomli_w

    config = {
        "auth": {
            "api_key": api_key,
        },
        "model": {
            "name": "deepseek-chat",
            "base_url": "https://api.deepseek.com",
        },
    }
    path = Path.home() / ".co-thinkerc"
    path.write_text("# Co-Thinker Global Configuration\n" + tomli_w.dumps(config), encoding="utf-8")


def _start_full_stack(web_dir: Path, port: int, api_port: int, cwd: Path, open_browser: bool = True) -> None:
    """同时启动 FastAPI 后端和 Next.js 前端。"""
    # 启动 API 服务
    api_proc = _start_api_process(api_port, cwd)

    # 检查 Node.js / npm
    typer.echo("[WEB] 检查 Node.js 环境...")
    if not _check_npm():
        typer.echo("[ERROR] 未检测到 npm，请先安装 Node.js (https://nodejs.org/)")
        typer.echo("[INFO] 仅启动 API 服务")
        _start_api_only(api_port, cwd)
        return

    # 安装前端依赖
    node_modules = web_dir / "node_modules"
    if not node_modules.exists():
        typer.echo("[WEB] 正在安装前端依赖 (npm install)...")
        result = subprocess.run(
            ["npm", "install"],
            cwd=str(web_dir),
        )
        if result.returncode != 0:
            typer.echo("[ERROR] npm install 失败，仅启动 API 服务")
            _start_api_only(api_port, cwd)
            return
        typer.echo("[WEB] 前端依赖安装完成")

    # 检测生产构建产物，决定启动模式
    next_build = web_dir / ".next"
    if next_build.exists():
        typer.echo(f"[WEB] 启动 Next.js 生产服务器 (port {port})...")
        mode_cmd = ["npx", "next", "start", "--port", str(port)]
    else:
        typer.echo(f"[WEB] 启动 Next.js 开发服务器 (port {port})...")
        mode_cmd = ["npx", "next", "dev", "--port", str(port)]

    env = os.environ.copy()
    env["NEXT_PUBLIC_API_URL"] = f"http://localhost:{api_port}"

    web_proc = subprocess.Popen(
        mode_cmd,
        cwd=str(web_dir),
        env=env,
    )

    if open_browser:
        import webbrowser
        webbrowser.open(f"http://localhost:{port}")

    typer.echo(f"[OK] API: http://localhost:{api_port}")
    typer.echo(f"[OK] Web: http://localhost:{port}")
    typer.echo("按 Ctrl+C 停止所有服务")

    try:
        api_proc.wait()
    except KeyboardInterrupt:
        typer.echo("\n[EXIT] 关闭中...")
        api_proc.terminate()
        web_proc.terminate()
        try:
            api_proc.wait(timeout=5)
            web_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            api_proc.kill()
            web_proc.kill()
        typer.echo("[OK] Co-Thinker 已关闭")


def _start_api_only(api_port: int, cwd: Path) -> None:
    """仅启动 FastAPI API 服务。"""
    proc = _start_api_process(api_port, cwd)
    typer.echo(f"[OK] API: http://localhost:{api_port}")
    typer.echo("按 Ctrl+C 停止服务")
    try:
        proc.wait()
    except KeyboardInterrupt:
        typer.echo("\n[EXIT] 关闭中...")
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        typer.echo("[OK] Co-Thinker 已关闭")


def _check_npm() -> bool:
    """检查 npm 是否可用。"""
    try:
        result = subprocess.run(
            ["npm", "--version"],
            capture_output=True,
            timeout=10,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _start_api_process(api_port: int, cwd: Path) -> subprocess.Popen:
    """启动 FastAPI 后端进程。"""
    typer.echo(f"[API] 启动 FastAPI 服务 (port {api_port})...")
    env = os.environ.copy()
    env["CO_THINKER_ROOT"] = str(cwd)

    api_module = "api.server:app"
    return subprocess.Popen(
        [
            sys.executable, "-m", "uvicorn", api_module,
            "--host", "0.0.0.0",
            "--port", str(api_port),
            "--log-level", "info",
        ],
        cwd=str(cwd),
        env=env,
    )


def _fmt_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes}B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f}KB"
    return f"{size_bytes / (1024*1024):.1f}MB"


# ═══════════════════════════════════════════════════════════════════════
#  Entry point
# ═══════════════════════════════════════════════════════════════════════


def main() -> None:
    """Console-scripts entry point (``co-thinker``)."""
    app()


if __name__ == "__main__":
    main()
