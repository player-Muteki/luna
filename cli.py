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
import shutil
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
    add_completion=False,
    invoke_without_command=True,
)


@app.callback(invoke_without_command=True)
def main_callback(
    ctx: typer.Context,
    version: bool = typer.Option(False, "--version", "-V", help="显示版本信息", is_eager=True),
) -> None:
    """基于 RAG 的工作目录知识库系统"""
    if version:
        print(_banner(__version__))
        raise typer.Exit()
    if ctx.invoked_subcommand is None:
        print(ctx.get_help())
        raise typer.Exit()


logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def _get_project_root() -> Path:
    """向上搜索 pyproject.toml 定位项目源码根目录。

    即使 cli.py 从 PYTHONPATH 目录（如 .local-pkgs/）加载，
    也能正确找到源码根目录。回退到 __file__ 所在目录。
    """
    candidate = Path(__file__).resolve().parent
    while candidate.parent != candidate:
        if (candidate / "pyproject.toml").is_file():
            return candidate
        candidate = candidate.parent
    return Path(__file__).resolve().parent


def _get_web_dir() -> Path:
    """返回 web 前端目录。

    优先通过项目源码根目录定位（兼容 PYTHONPATH 干扰场景），
    回退到 __file__ 所在目录的 web/。
    """
    root = _get_project_root()
    web = root / "web"
    if web.is_dir():
        return web
    return Path(__file__).resolve().parent / "web"


def _sanitize_env(keep_pythonpath: bool = False) -> dict[str, str]:
    """构建子进程环境变量。

    清除继承的 PYTHONPATH 中指向项目内部的缓存路径（如 .local-pkgs），
    避免子进程加载过时的原生扩展（如 Python 版本升级后的 .so 不兼容）。
    """
    env = os.environ.copy()
    if not keep_pythonpath and "PYTHONPATH" in env:
        pp = env["PYTHONPATH"]
        cleaned = []
        for p in pp.split(os.pathsep):
            p_stripped = p.strip()
            if p_stripped and ".local-pkgs" not in p_stripped:
                cleaned.append(p_stripped)
        if cleaned:
            env["PYTHONPATH"] = os.pathsep.join(cleaned)
        else:
            env.pop("PYTHONPATH", None)
    return env


def _banner(version: str) -> str:
    return BANNER.format(version=version)


def _setup_project_context() -> object:
    """Create and wire up a WorkspaceRuntime with all engines."""
    from core.runtime import WorkspaceRuntime

    return WorkspaceRuntime.bootstrap()


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
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "tomli-w"],
                capture_output=True, timeout=60,
            )
            if result.returncode == 0:
                try:
                    import tomli_w  # type: ignore[import-untyped]
                except ImportError:
                    typer.echo("[WARN] 无法安装 tomli-w，跳过 config.toml 创建")
                    config_path = None
            else:
                typer.echo("[WARN] pip install tomli-w 失败，跳过 config.toml 创建")
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

    web_dir = _get_web_dir()

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

    runtime = _setup_project_context()

    # 一次性问答（自动处理索引 → 检索 → 生成）
    result = runtime.ask(query)

    # 索引反馈
    if result.indexed_file_count > 0:
        typer.echo(f"[INFO] 已自动索引 {result.indexed_file_count} 个文件，共 {result.indexed_chunk_count} 个片段")
    elif result.indexed_file_count == 0 and result.references:
        # 已有数据，无需索引
        pass

    # 检索反馈
    if result.retrieval_details and result.references:
        typer.echo(f"[R] 共检索到 {len(result.references)} 个相关片段（{result.retrieval_details['mode']} 模式）")

    # 没有结果
    if not result.references:
        typer.echo("[INFO] 知识库中未找到相关信息")
        if result.answer:
            typer.echo("")
            typer.echo(result.answer)
        raise typer.Exit(0)

    # 显示推理过程（如果有）
    if result.reasoning:
        typer.echo("")
        typer.echo(result.reasoning)

    # 答案是最后显示
    typer.echo("")
    typer.echo(result.answer)
    typer.echo("")

    # 显示引用来源
    if result.references:
        typer.echo("── 引用来源 ──")
        for i, ref in enumerate(result.references[:5], 1):
            typer.echo(f"  [{i}] {ref.get('source_path', 'unknown')} (score: {ref.get('score', 0):.3f})")


@app.command()
def scan(
    dir: str = typer.Option(None, "--dir", help="项目目录（默认当前目录）"),
):
    """扫描工作目录，显示文件索引状态"""
    from core.runtime import WorkspaceRuntime

    scan_dir = Path(dir).resolve() if dir else Path.cwd().resolve()
    runtime = WorkspaceRuntime.bootstrap(str(scan_dir))
    files = runtime.scan_files()

    files_only = [f for f in files if not f["is_dir"]]
    dirs_only = [f for f in files if f["is_dir"]]

    indexed = sum(1 for f in files_only if f["is_indexed"])
    total = len(files_only)

    typer.echo(f"工作目录: {scan_dir}")
    typer.echo(f"文件总数: {total}, 已索引: {indexed}")
    typer.echo("")

    # 显示文件树
    for d in dirs_only:
        typer.echo(f"  📁 {d['path']}/")
    for f in files_only:
        status = "☑" if f["is_indexed"] else "☐"
        typer.echo(f"  {status} {f['path']} ({_fmt_size(f['size'])})")


def _npm_cmd() -> list[str]:
    """返回跨平台的 npm 命令列表。"""
    if sys.platform == "win32":
        return ["npm.cmd"]
    return ["npm"]


def _npx_cmd() -> list[str]:
    """返回跨平台的 npx 命令列表。"""
    if sys.platform == "win32":
        return ["npx.cmd"]
    return ["npx"]


@app.command()
def upgrade(
    yes: bool = typer.Option(False, "--yes", "-y", help="跳过确认提示"),
) -> None:
    """将 Co-Thinker 更新到最新版本"""
    import json
    import urllib.request
    import urllib.error

    print(_banner(__version__))

    # 1. 获取当前版本
    typer.echo(f"当前版本: {__version__}")

    # 2. 获取线上最新版本
    repo = "player-Muteki/co-thinker"
    api_url = f"https://api.github.com/repos/{repo}/releases/latest"
    typer.echo("[INFO] 正在检查更新...")

    try:
        req = urllib.request.Request(api_url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
    except (urllib.error.URLError, json.JSONDecodeError, OSError) as e:
        typer.echo(f"[ERROR] 无法获取最新版本信息: {e}")
        raise typer.Exit(1)

    latest_tag = data.get("tag_name", "")
    latest_version = latest_tag.lstrip("v") if latest_tag else ""
    if not latest_version:
        typer.echo("[ERROR] 无法解析最新版本号")
        raise typer.Exit(1)

    # 获取 wheel 下载 URL
    wheel_url = None
    for asset in data.get("assets", []):
        if asset.get("name", "").endswith(".whl"):
            wheel_url = asset.get("browser_download_url")
            break

    typer.echo(f"最新版本: {latest_version}")

    # 3. 比较版本号
    from packaging.version import parse as parse_version
    if parse_version(latest_version) <= parse_version(__version__):
        typer.echo("[OK] 已是最新版本，无需更新")
        raise typer.Exit()

    typer.echo(f"[NEW] 发现新版本: {__version__} → {latest_version}")

    if not wheel_url:
        typer.echo("[ERROR] 未找到可下载的 wheel 文件")
        raise typer.Exit(1)

    # 4. 确认或跳过
    if not yes:
        if not typer.confirm("是否现在更新?", default=True):
            typer.echo("[SKIP] 已取消")
            raise typer.Exit()

    # 5. 下载 wheel
    typer.echo("[INFO] 正在下载最新版本...")
    import tempfile
    tmp_dir = tempfile.mkdtemp()
    wheel_name = wheel_url.split("/")[-1]
    wheel_path = Path(tmp_dir) / wheel_name

    try:
        urllib.request.urlretrieve(wheel_url, str(wheel_path))
    except (urllib.error.URLError, OSError) as e:
        typer.echo(f"[ERROR] 下载失败: {e}")
        raise typer.Exit(1)

    typer.echo(f"[OK] 下载完成: {wheel_name}")

    # 6. pip install --upgrade
    typer.echo("[INFO] 正在安装更新...")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "--upgrade", str(wheel_path)],
        capture_output=True, text=True, timeout=120,
    )
    if result.returncode != 0:
        typer.echo(f"[ERROR] 安装失败:\n{result.stderr}")
        raise typer.Exit(1)

    typer.echo("[OK] 更新完成！")
    typer.echo(f"版本: {latest_version}")

    # 清理临时文件
    import shutil
    shutil.rmtree(tmp_dir, ignore_errors=True)


@app.command()
def version():
    """显示版本与系统信息（快捷方式：co-thinker --version）"""
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
    if sys.platform != "win32":
        os.chmod(path, 0o600)


def _start_full_stack(web_dir: Path, port: int, api_port: int, cwd: Path, open_browser: bool = True) -> None:
    """同时启动 FastAPI 后端和 Next.js 前端。"""
    api_proc = _start_api_process(api_port, cwd)

    typer.echo("[WEB] 检查 Node.js 环境...")
    if not _ensure_npm_available():
        typer.echo("[ERROR] 未检测到 npm，请先安装 Node.js (https://nodejs.org/)")
        typer.echo("[INFO] 仅启动 API 服务")
        _start_api_only(api_port, cwd)
        return

    if not _install_frontend_deps(web_dir):
        _start_api_only(api_port, cwd)
        return

    env = _sanitize_env(keep_pythonpath=False)
    env["NEXT_PUBLIC_API_URL"] = f"http://localhost:{api_port}"
    web_proc = _start_nextjs(web_dir, port, env)

    if open_browser:
        _open_browser(port)

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


def _install_frontend_deps(web_dir: Path) -> bool:
    """安装前端 npm 依赖，成功返回 True。"""
    node_modules = web_dir / "node_modules"
    if node_modules.exists():
        return True
    typer.echo("[WEB] 正在安装前端依赖 (npm install)...")
    result = subprocess.run([*_npm_cmd(), "install"], cwd=str(web_dir))
    if result.returncode != 0:
        typer.echo("[ERROR] npm install 失败")
        return False
    typer.echo("[WEB] 前端依赖安装完成")
    return True


def _start_nextjs(web_dir: Path, port: int, env: dict[str, str]) -> subprocess.Popen:
    """启动 Next.js 前端进程（生产模式，必要时自动构建）。"""
    next_build = web_dir / ".next"
    build_manifest = next_build / "build-manifest.json"
    if next_build.exists() and build_manifest.exists():
        typer.echo(f"[WEB] 启动 Next.js 生产服务器 (port {port})...")
        cmd = [*_npx_cmd(), "next", "start", "--port", str(port)]
    else:
        typer.echo("[WEB] 未检测到构建产物，正在构建前端...")
        typer.echo("[WEB] 首次构建可能需要 30-60 秒...")
        build_result = subprocess.run(
            [*_npx_cmd(), "next", "build"], cwd=str(web_dir),
            capture_output=False,
        )
        if build_result.returncode != 0:
            typer.echo("[ERROR] Next.js 构建失败，启动开发服务器作为降级...")
            cmd = [*_npx_cmd(), "next", "dev", "--port", str(port)]
        else:
            typer.echo(f"[WEB] 构建完成，启动生产服务器 (port {port})...")
            cmd = [*_npx_cmd(), "next", "start", "--port", str(port)]
    return subprocess.Popen(cmd, cwd=str(web_dir), env=env)


def _open_browser(port: int) -> None:
    """在默认浏览器中打开指定端口。"""
    import webbrowser
    webbrowser.open(f"http://localhost:{port}")


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


def _ensure_npm_available() -> bool:
    """检测并确保 npm 在 PATH 中可用。"""
    npm_cmd = _npm_cmd()[0]
    if shutil.which(npm_cmd) is not None:
        return True
    if sys.platform == "win32" and shutil.which("npm") is not None:
        return True
    _add_node_paths()

    try:
        subprocess.run([*_npm_cmd(), "--version"], capture_output=True, timeout=10, check=True)
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired, subprocess.CalledProcessError):
        return False


def _add_node_paths() -> None:
    """将常见 Node.js 安装路径加入 PATH（如未包含）。"""
    if sys.platform == "win32":
        candidates = [
            os.path.expanduser("~\\AppData\\Roaming\\npm"),
            os.path.expandvars("%ProgramFiles%\\nodejs"),
            os.path.expandvars("%ProgramFiles(x86)%\\nodejs"),
        ]
    else:
        candidates = [
            "/opt/homebrew/bin",
            "/usr/local/bin",
            os.path.expanduser("~/.nvm/versions/node/*/bin"),
        ]
    for path in candidates:
        if "*" in path:
            import glob
            matches = glob.glob(path)
            if matches:
                os.environ.setdefault("PATH", f"{matches[-1]}{os.pathsep}{os.environ.get('PATH', '')}")
        else:
            os.environ.setdefault("PATH", f"{path}{os.pathsep}{os.environ.get('PATH', '')}")


def _start_api_process(api_port: int, cwd: Path) -> subprocess.Popen:
    """启动 FastAPI 后端进程。"""
    typer.echo(f"[API] 启动 FastAPI 服务 (port {api_port})...")
    env = _sanitize_env(keep_pythonpath=False)
    env["CO_THINKER_ROOT"] = str(cwd)

    # 如果运行在源码环境，确保 PYTHONPATH 指向项目根目录，
    # 使 API 子进程能正确导入 core/、api/ 等模块。
    source_root = _get_project_root()
    if source_root.joinpath("pyproject.toml").exists():
        existing = env.get("PYTHONPATH", "")
        if existing:
            env["PYTHONPATH"] = f"{source_root}{os.pathsep}{existing}"
        else:
            env["PYTHONPATH"] = str(source_root)

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
