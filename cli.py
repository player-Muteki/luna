"""
Co-Thinker CLI — Launch the web UI from the terminal.

Works in both development mode (``python cli.py start``) and installed mode
(``co-thinker start`` after ``pip install``).

Usage:
    co-thinker start              Launch the Streamlit web UI
    co-thinker start --port 8080
    co-thinker init               Set up a working directory
    co-thinker version             Show version
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import typer

from __version__ import __version__

BANNER = r"""
   ____          _   _   _           _
  / ___|___   __| | | |_| |__  _ __ | | _____ _ __
 | |   / _ \ / _` | | __| '_ \| '_ \| |/ / _ \ '__|
 | |__| (_) | (_| | | |_| | | | | | |   <  __/ |
  \____\___/ \__,_|  \__|_| |_|_| |_|_|\_\___|_|

  基于 RAG 的本地知识问答系统  v{version}
"""

app = typer.Typer(
    name="co-thinker",
    help="基于 RAG 的本地知识问答系统",
    no_args_is_help=True,
    add_completion=False,
)

# ── helpers ──────────────────────────────────────────────────────────


def _find_streamlit_app() -> Path:
    """Locate ``app/streamlit_app.py`` whether we are installed or in source tree."""
    candidates = [
        # Installed mode: cli.py is in site-packages/, app/ is sibling
        Path(__file__).resolve().parent / "app" / "streamlit_app.py",
        # Dev mode: cli.py is at project root, app/ is child
        Path(__file__).resolve().parent / "app" / "streamlit_app.py",
    ]
    # Deduplicate (both resolve to same path in dev mode)
    seen: set[Path] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        if candidate.exists():
            return candidate
    raise typer.Exit(
        "❌ 找不到 app/streamlit_app.py。"
        "请确认 Co-Thinker 已正确安装 (pip install) 或在项目根目录下运行。"
    )


def _banner(version: str) -> str:
    return BANNER.format(version=version)


def _ensure_runtime_dirs(cwd: Path) -> None:
    """Create runtime directories in the user's working directory if missing."""
    for name in ("data", "vectorstore", "storage"):
        (cwd / name).mkdir(parents=True, exist_ok=True)


def _prompt_env(cwd: Path) -> Path | None:
    """Create a .env file if missing, return its path or None."""
    env_path = cwd / ".env"
    if env_path.exists():
        return env_path

    typer.echo("⚠️  未检测到 .env 文件。")
    if not typer.confirm("  是否现在创建？（需要填入 DeepSeek API Key）", default=True):
        return None

    api_key = typer.prompt("  DeepSeek API Key", hide_input=True)
    if not api_key:
        typer.echo("  ⏭ 跳过，稍后可手动创建 .env")
        return None

    template = f"""# Co-Thinker 配置 — 由 `co-thinker init` 自动生成
DEEPSEEK_API_KEY={api_key}
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
DATA_DIR=data
VECTORSTORE_DIR=vectorstore
STORAGE_DIR=storage
CHUNK_SIZE=800
CHUNK_OVERLAP=120
TOP_K=5
RETRIEVAL_CANDIDATE_K=20
SIMILARITY_CUTOFF=0.25
RRF_K=60
VECTOR_WEIGHT=0.55
BM25_WEIGHT=0.45
MAX_TOKENS=2048
TEMPERATURE=0.2
CONTEXT_TOKEN_BUDGET=6000
MAX_HISTORY_TURNS=10
LOG_LEVEL=INFO
"""
    env_path.write_text(template, encoding="utf-8")
    typer.echo(f"  ✅ .env 已创建: {env_path}")
    return env_path


# ── commands ─────────────────────────────────────────────────────────


@app.command()
def init(
    dir: Path = typer.Argument(
        ".",
        help="工作目录（默认当前目录）",
    ),
):
    """在当前目录初始化工作环境（创建 .env 和运行时目录）"""
    cwd = dir.resolve()
    cwd.mkdir(parents=True, exist_ok=True)

    print(_banner(__version__))
    typer.echo(f"📂 工作目录: {cwd}")
    typer.echo("")

    _ensure_runtime_dirs(cwd)
    typer.echo("✅ 已创建: data/  vectorstore/  storage/")

    env_path = cwd / ".env"
    if env_path.exists():
        typer.echo(f"✅ 已存在: .env")
    else:
        _prompt_env(cwd)

    typer.echo("")
    typer.echo("🎉 初始化完成！运行 co-thinker start 启动 Web 界面。")


@app.command()
def start(
    port: int = typer.Option(8501, "--port", "-p", help="Web UI 端口号"),
    open_browser: bool = typer.Option(True, "--open/--no-open", help="启动后自动打开浏览器"),
    debug: bool = typer.Option(False, "--debug", "-d", help="显示 Streamlit 详情日志"),
):
    """启动 Co-Thinker Web 界面"""
    streamlit_app = _find_streamlit_app()
    cwd = Path.cwd().resolve()

    print(_banner(__version__))
    typer.echo(f"🔌 端口: {port}")
    typer.echo(f"📂 工作目录: {cwd}")
    typer.echo(f"📄 应用入口: {streamlit_app}")
    typer.echo("")

    # 确保运行时目录存在
    _ensure_runtime_dirs(cwd)

    # 检查 .env
    env = os.environ.copy()
    if not (cwd / ".env").exists():
        typer.echo("⚠️  工作目录中未找到 .env 文件。")
        typer.echo("   运行 co-thinker init 来创建，或手动创建 .env 后重试。")
        typer.echo("   当前会尝试读取已有的环境变量。")
        typer.echo("")

    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(streamlit_app),
        "--server.port",
        str(port),
    ]
    if debug:
        cmd.extend(["--logger.level", "debug"])
    else:
        cmd.extend(["--logger.level", "warning"])

    if open_browser:
        import webbrowser

        webbrowser.open(f"http://localhost:{port}")

    try:
        typer.echo("⏳ 正在启动...")
        process = subprocess.Popen(cmd, cwd=str(cwd), env=env)
        process.wait()
    except KeyboardInterrupt:
        typer.echo("\n👋 关闭中...")
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
        typer.echo("✅ Co-Thinker 已关闭")


@app.command()
def version():
    """显示版本与系统信息"""
    print(_banner(__version__))

    # 检测安装方式
    import app as _app_pkg

    installed_path = Path(__file__).resolve().parent
    in_site_packages = "site-packages" in installed_path.parts

    typer.echo(f"版本:      {__version__}")
    typer.echo(f"安装方式:  {'pip 安装' if in_site_packages else '源码运行'}")
    typer.echo(f"包路径:    {installed_path}")
    typer.echo(f"Python:    {sys.version.split()[0]}")


# ── entry point ──────────────────────────────────────────────────────


def main() -> None:
    """Console-scripts entry point (``co-thinker``)."""
    app()


if __name__ == "__main__":
    main()
