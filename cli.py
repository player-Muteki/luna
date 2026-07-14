"""
Luna CLI — 工作目录绑定型 RAG 知识库系统。

Usage:
    luna init                   在当前目录创建 .luna/ + 默认配置
    luna start                  启动 API 服务
    luna run "问题"             非交互式一键问答
    luna scan                   扫描工作目录，显示文件索引状态
    luna version                显示版本
"""

from __future__ import annotations

import logging
import os
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

import typer

from __version__ import __version__

BANNER_GOLD = "\033[38;5;220m"
BANNER_GRAY = "\033[38;5;244m"
BANNER_DIM = "\033[38;5;239m"
BANNER_RESET = "\033[0m"


app = typer.Typer(
    name="luna",
    help="基于 RAG 的工作目录知识库系统",
    add_completion=False,
    invoke_without_command=True,
)
agent_app = typer.Typer(help="知识库 Agent 命令")
app.add_typer(agent_app, name="agent")


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


def _sanitize_env() -> dict[str, str]:
    """构建子进程环境变量，清除继承的 PYTHONPATH 中指向项目内部的缓存路径。

    避免子进程加载过时的原生扩展（如 Python 版本升级后的 .so 不兼容）。
    """
    env = os.environ.copy()
    if "PYTHONPATH" in env:
        pp = env["PYTHONPATH"]
        cleaned = [p for p in pp.split(os.pathsep) if p.strip() and ".local-pkgs" not in p]
        if cleaned:
            env["PYTHONPATH"] = os.pathsep.join(cleaned)
        else:
            env.pop("PYTHONPATH", None)
    return env


def _banner(version: str) -> str:
    try:
        art = _render_ascii_banner()
    except Exception:
        art = "luna"
    return (
        f"{BANNER_GOLD}{art}{BANNER_RESET}\n"
        f"  {BANNER_GRAY}基于 RAG 的工作目录知识库{BANNER_RESET}\n"
        f"  {BANNER_DIM}v{version}{BANNER_RESET}\n"
    )


def _render_ascii_banner() -> str:
    return _join_ascii_blocks(_render_ascii_moon(), _render_ascii_text())


def _render_ascii_moon() -> str:
    from PIL import Image, ImageDraw

    width, height = 16, 8
    size = 300
    image = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(image)
    draw.ellipse((30, 28, 278, 274), fill=255)
    draw.ellipse((108, 14, 310, 262), fill=0)

    bbox = image.getbbox()
    if bbox:
        image = image.crop(bbox)

    image = image.resize((width, height), Image.Resampling.LANCZOS)
    pixels = image.load()

    chars = []
    for y in range(height):
        row = []
        for x in range(width):
            v = pixels[x, y]
            if v >= 208:
                row.append("█")
            elif v >= 144:
                row.append("▓")
            elif v >= 80:
                row.append("▒")
            elif v >= 24:
                row.append("░")
            else:
                row.append(" ")
        line = "".join(row).rstrip()
        if line.strip():
            chars.append(line)

    return "\n".join(chars)


def _render_ascii_text() -> str:
    import pyfiglet

    return pyfiglet.figlet_format("luna", font="ansi_shadow", width=120).rstrip()


def _join_ascii_blocks(left: str, right: str, gap: int = 4) -> str:
    left_lines = left.splitlines()
    right_lines = right.splitlines()
    height = max(len(left_lines), len(right_lines))
    left_width = max(len(line) for line in left_lines)
    top_padding = max(0, (height - len(left_lines)) // 2)
    left_lines = [""] * top_padding + left_lines + [""] * (height - len(left_lines) - top_padding)
    right_lines = right_lines + [""] * (height - len(right_lines))
    return "\n".join(
        f"{left_line:<{left_width}}{' ' * gap}{right_line}".rstrip()
        for left_line, right_line in zip(left_lines, right_lines)
    )


def _setup_project_context(explicit_root: str | None = None) -> object:
    """Create and wire up a WorkspaceRuntime with all engines."""
    from core.runtime import WorkspaceRuntime

    return WorkspaceRuntime.bootstrap(explicit_root)


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
    """在当前目录初始化知识库配置目录"""
    cwd = dir.resolve()
    cwd.mkdir(parents=True, exist_ok=True)

    print(_banner(__version__))
    typer.echo(f"[DIR] 工作目录: {cwd}")
    typer.echo("")

    co_dir = cwd / ".luna"
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

    # 检查全局配置 ~/.lunarc
    from core.project import GLOBAL_CONFIG_PATH, _load_global_config

    if not GLOBAL_CONFIG_PATH.exists():
        typer.echo("")
        typer.echo(f"[WARN] 未检测到全局配置 ~/.lunarc")
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
    typer.echo("[DONE] 初始化完成！运行 luna start 启动 API 服务。")


@app.command()
def start(
    port: int = typer.Option(8765, "--port", "-p", help="API 服务端口号"),
):
    """启动 FastAPI API 服务"""
    cwd = Path.cwd().resolve()
    print(_banner(__version__))
    typer.echo(f"[DIR] 工作目录: {cwd}")

    # 检查 .luna 是否存在
    co_dir = cwd / ".luna"
    if not co_dir.exists():
        typer.echo("[WARN] 未检测到 .luna/ 目录。请先运行 luna init。")
        typer.echo("")
        if not typer.confirm("是否现在就初始化？", default=True):
            raise typer.Exit(1)
        init(dir=cwd)
        typer.echo("")

    os.environ.setdefault("LUNA_ROOT", str(cwd))

    _start_api(port, cwd)


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

    runtime = _setup_project_context(dir)

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


def _emit_agent_events(events, *, json_output: bool = False) -> None:
    for event in events:
        payload = event.to_dict()
        if json_output:
            typer.echo(json.dumps(payload, ensure_ascii=False))
            continue

        event_type = payload["type"]
        if event_type == "tool_call_start":
            typer.echo(f"[tool] {payload.get('tool_name')} {json.dumps(payload.get('arguments', {}), ensure_ascii=False)}")
        elif event_type == "tool_call_result":
            typer.echo(f"[result] {payload.get('tool_name')}")
            if payload.get("body"):
                typer.echo(json.dumps(payload["body"], ensure_ascii=False, indent=2))
        elif event_type == "approval_required":
            typer.echo(f"[approval_required] {payload.get('tool_name')}")
            if payload.get("approval_id"):
                typer.echo(f"approval_id: {payload['approval_id']}")
            if payload.get("message"):
                typer.echo(payload["message"])
        elif event_type == "plan_created":
            typer.echo(f"[plan] {payload.get('plan_id')}")
            if payload.get("message"):
                typer.echo(payload["message"])
        elif event_type == "error":
            typer.echo(f"[error] {payload.get('error')}")
        elif payload.get("message"):
            typer.echo(payload["message"])


@agent_app.callback()
def agent() -> None:
    """知识库 Agent 命令。"""


@agent_app.command("run")
def agent_run(
    goal: str = typer.Argument(..., help="Agent 目标"),
    plan: bool = typer.Option(False, "--plan", help="只读计划模式"),
    goal_mode: bool = typer.Option(False, "--goal", help="目标模式"),
    yes: bool = typer.Option(False, "--yes", "-y", help="自动执行低风险变更工具"),
    respond: bool = typer.Option(False, "--respond", "-r", help="执行后生成 LLM 响应总结"),
    dir: str | None = typer.Option(None, "--dir", help="项目目录（默认当前目录）"),
    json_output: bool = typer.Option(False, "--json", help="输出 JSONL 事件"),
) -> None:
    """运行知识库 Agent。"""
    from core.agent_modes import AgentMode, ApprovalMode

    mode = AgentMode.PLAN if plan else AgentMode.GOAL if goal_mode else AgentMode.DEFAULT
    approval_mode = ApprovalMode.AUTO_SAFE_MUTATION if yes else ApprovalMode.ASK
    runtime = _setup_project_context(dir)
    events = runtime.get_agent_workflow().execute(
        goal,
        mode=mode,
        approval_mode=approval_mode,
        generate_response=respond,
    )
    _emit_agent_events(events, json_output=json_output)


@agent_app.command("plans")
def agent_plans(
    dir: str | None = typer.Option(None, "--dir", help="项目目录（默认当前目录）"),
    json_output: bool = typer.Option(False, "--json", help="输出 JSON"),
) -> None:
    """列出已保存的 Agent 计划。"""
    runtime = _setup_project_context(dir)
    plans = [plan.to_dict() for plan in runtime.get_agent_workflow().list_plans()]
    if json_output:
        typer.echo(json.dumps({"plans": plans}, ensure_ascii=False, indent=2))
        return
    for plan in plans:
        typer.echo(f"{plan['id']}  {plan['status']}  {plan['goal']}")


@agent_app.command("approvals")
def agent_approvals(
    dir: str | None = typer.Option(None, "--dir", help="项目目录（默认当前目录）"),
    json_output: bool = typer.Option(False, "--json", help="输出 JSON"),
) -> None:
    """列出待审批的 Agent 工具调用。"""
    runtime = _setup_project_context(dir)
    approvals = [approval.to_dict() for approval in runtime.get_agent_workflow().list_approvals()]
    if json_output:
        typer.echo(json.dumps({"approvals": approvals}, ensure_ascii=False, indent=2))
        return
    for approval in approvals:
        typer.echo(f"{approval['id']}  {approval['status']}  {approval['tool_name']}  {approval['reason']}")


@agent_app.command("approve")
def agent_approve(
    approval_id: str = typer.Argument(..., help="审批 ID"),
    dir: str | None = typer.Option(None, "--dir", help="项目目录（默认当前目录）"),
    json_output: bool = typer.Option(False, "--json", help="输出 JSON"),
) -> None:
    """批准并执行一个 Agent 工具调用。"""
    runtime = _setup_project_context(dir)
    workflow = runtime.get_agent_workflow()
    approval = workflow.approve(approval_id)
    payload = approval.to_dict()
    if json_output:
        typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        typer.echo(f"[approved] {approval.id} {approval.tool_name}")

    events = workflow.execute_approved(approval_id)
    _emit_agent_events(events, json_output=json_output)


@agent_app.command("reject")
def agent_reject(
    approval_id: str = typer.Argument(..., help="审批 ID"),
    dir: str | None = typer.Option(None, "--dir", help="项目目录（默认当前目录）"),
    json_output: bool = typer.Option(False, "--json", help="输出 JSON"),
) -> None:
    """拒绝一个 Agent 工具调用。"""
    runtime = _setup_project_context(dir)
    approval = runtime.get_agent_workflow().reject(approval_id)
    payload = approval.to_dict()
    if json_output:
        typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    typer.echo(f"[rejected] {approval.id} {approval.tool_name}")


@agent_app.command("sessions")
def agent_sessions(
    dir: str | None = typer.Option(None, "--dir", help="项目目录（默认当前目录）"),
    json_output: bool = typer.Option(False, "--json", help="输出 JSON"),
) -> None:
    """列出 Agent 会话。"""
    runtime = _setup_project_context(dir)
    sessions = [session.to_dict() for session in runtime.get_agent_workflow().list_sessions()]
    if json_output:
        typer.echo(json.dumps({"sessions": sessions}, ensure_ascii=False, indent=2))
        return
    for session in sessions:
        typer.echo(f"{session['id']}  {session['status']}  {session['mode']}  {session['goal']}")


@agent_app.command("show")
def agent_show(
    session_id: str = typer.Argument(..., help="Agent session ID"),
    dir: str | None = typer.Option(None, "--dir", help="项目目录（默认当前目录）"),
) -> None:
    """显示 Agent 会话事件。"""
    runtime = _setup_project_context(dir)
    typer.echo(json.dumps({"events": runtime.get_agent_workflow().read_session(session_id)}, ensure_ascii=False, indent=2))


@app.command()
def tool(
    name: str = typer.Argument(..., help="工具名"),
    arguments: str = typer.Argument("{}", help="JSON 参数"),
    dir: str | None = typer.Option(None, "--dir", help="项目目录（默认当前目录）"),
) -> None:
    """通过 Rust agent runtime 调用知识库工具。"""
    try:
        parsed_arguments = json.loads(arguments)
    except json.JSONDecodeError as exc:
        typer.echo(f"[ERROR] arguments 不是合法 JSON: {exc}")
        raise typer.Exit(1)

    if not isinstance(parsed_arguments, dict):
        typer.echo("[ERROR] arguments 必须是 JSON object")
        raise typer.Exit(1)

    runtime = _setup_project_context(dir)

    try:
        response = runtime.get_agent_runtime().call_tool(name, parsed_arguments)
    except Exception as exc:
        typer.echo(f"[ERROR] {exc}")
        raise typer.Exit(1)

    typer.echo(json.dumps(response, ensure_ascii=False, indent=2))


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


@app.command()
def upgrade(
    yes: bool = typer.Option(False, "--yes", "-y", help="跳过确认提示"),
) -> None:
    """将 Luna 更新到最新版本"""
    print(_banner(__version__))
    typer.echo(f"当前版本: {__version__}")

    latest, wheel_url, wheel_sha = _fetch_latest_release_info()
    typer.echo(f"最新版本: {latest}")

    if not _is_newer_version(latest, __version__):
        typer.echo("[OK] 已是最新版本，无需更新")
        raise typer.Exit()

    typer.echo(f"[NEW] 发现新版本: {__version__} → {latest}")

    if not wheel_url:
        typer.echo("[ERROR] 未找到可下载的 wheel 文件")
        raise typer.Exit(1)

    if not yes and not typer.confirm("是否现在更新?", default=True):
        typer.echo("[SKIP] 已取消")
        raise typer.Exit()

    wheel_path = _download_wheel(wheel_url, wheel_sha)
    _install_wheel(wheel_path)
    _cleanup_temp(wheel_path.parent)

    typer.echo("[OK] 更新完成！")
    typer.echo(f"版本: {latest}")

@app.command()
def version():
    """显示版本与系统信息（快捷方式：luna --version）"""
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

def _fetch_latest_release_info() -> tuple[str, str | None, str | None]:
    """获取 GitHub 最新 release 的版本号、wheel URL 和 SHA256。"""
    import json
    import urllib.request
    import urllib.error

    repo = "player-Muteki/luna"
    api_url = f"https://api.github.com/repos/{repo}/releases/latest"
    typer.echo("[INFO] 正在检查更新...")

    try:
        headers = {"Accept": "application/json"}
        gh_token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""
        if gh_token:
            headers["Authorization"] = f"Bearer {gh_token}"
        req = urllib.request.Request(api_url, headers=headers)
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

    wheel_url: str | None = None
    wheel_sha: str | None = None
    for asset in data.get("assets", []):
        if asset.get("name", "").endswith(".whl"):
            wheel_url = asset.get("browser_download_url")
            wheel_sha = asset.get("sha256") or None
            break

    return latest_version, wheel_url, wheel_sha


def _is_newer_version(latest: str, current: str) -> bool:
    """比较版本号，latest > current 返回 True。"""
    try:
        from packaging.version import parse as parse_version
        return parse_version(latest) > parse_version(current)
    except ImportError:
        return latest != current


def _download_wheel(wheel_url: str, expected_sha: str | None) -> Path:
    """下载 wheel 文件并校验 SHA256（如果提供了）。返回下载后的路径。"""
    import hashlib
    import tempfile
    import urllib.request
    import urllib.error

    typer.echo("[INFO] 正在下载最新版本...")
    tmp_dir = tempfile.mkdtemp()
    wheel_name = wheel_url.split("/")[-1]
    wheel_path = Path(tmp_dir) / wheel_name

    try:
        urllib.request.urlretrieve(wheel_url, str(wheel_path))
    except (urllib.error.URLError, OSError) as e:
        typer.echo(f"[ERROR] 下载失败: {e}")
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise typer.Exit(1)

    if expected_sha:
        _verify_wheel_sha(wheel_path, expected_sha)

    typer.echo(f"[OK] 下载完成: {wheel_name}")
    return wheel_path


def _verify_wheel_sha(wheel_path: Path, expected_sha: str) -> None:
    """校验 wheel 文件的 SHA256 哈希。"""
    import hashlib

    actual_sha = hashlib.sha256(wheel_path.read_bytes()).hexdigest()
    if actual_sha != expected_sha:
        typer.echo("[ERROR] wheel 校验失败: SHA256 不匹配")
        typer.echo(f"  期望: {expected_sha}")
        typer.echo(f"  实际: {actual_sha}")
        shutil.rmtree(wheel_path.parent, ignore_errors=True)
        raise typer.Exit(1)
    typer.echo("[OK] wheel 校验通过")


def _install_wheel(wheel_path: Path) -> None:
    """pip install --upgrade wheel 文件。"""
    typer.echo("[INFO] 正在安装更新...")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "--upgrade", str(wheel_path)],
        capture_output=True, text=True, timeout=120,
    )
    if result.returncode != 0:
        typer.echo(f"[ERROR] 安装失败:\n{result.stderr}")
        typer.echo(f"[INFO] 可手动回滚: pip install luna=={__version__}")
        shutil.rmtree(wheel_path.parent, ignore_errors=True)
        raise typer.Exit(1)


def _cleanup_temp(tmp_dir: Path) -> None:
    """清理临时下载目录。"""
    shutil.rmtree(tmp_dir, ignore_errors=True)


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
    path.write_text("# Luna Project Configuration\n" + tw.dumps(config), encoding="utf-8")


def _write_global_config(api_key: str) -> None:
    """创建 ~/.lunarc 全局配置文件。"""
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
    path = Path.home() / ".lunarc"
    path.write_text("# Luna Global Configuration\n" + tomli_w.dumps(config), encoding="utf-8")
    if sys.platform != "win32":
        os.chmod(path, 0o600)


def _start_api(api_port: int, cwd: Path) -> None:
    """启动 FastAPI API 服务。"""
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
        typer.echo("[OK] Luna 已关闭")


def _start_api_process(api_port: int, cwd: Path) -> subprocess.Popen:
    """启动 FastAPI 后端进程。"""
    typer.echo(f"[API] 启动 FastAPI 服务 (port {api_port})...")
    env = _sanitize_env()
    env["LUNA_ROOT"] = str(cwd)

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
    """Console-scripts entry point (``luna``)."""
    app()


if __name__ == "__main__":
    main()
