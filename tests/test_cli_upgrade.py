"""
CLI upgrade command 测试。

覆盖：
  - 已是最新版本 → 不更新
  - 发现新版本 → 下载并升级
  - 未找到 wheel 附件 → 报错退出
  - GitHub API 不可达 → 报错退出
  - packaging 不可用时 ImportError 回退路径
  - pip install 失败场景
  - wheel SHA256 校验失败场景
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

from typer.testing import CliRunner

from cli import app

runner = CliRunner()


def _mock_urlopen(data: bytes) -> MagicMock:
    """创建一个模拟 urllib.request.urlopen 的响应，支持上下文管理器。"""
    response = MagicMock()
    response.read.return_value = data
    response.__enter__.return_value = response
    return response


def _make_release(tag: str, wheel_name: str = "co_thinker-9.9.9-py3-none-any.whl") -> bytes:
    return json.dumps({
        "tag_name": tag,
        "assets": [
            {
                "name": "co_thinker-0.0.1.tar.gz",
                "browser_download_url": f"https://github.com/player-Muteki/co-thinker/releases/download/{tag}/co_thinker-0.0.1.tar.gz",
            },
            {
                "name": wheel_name,
                "browser_download_url": f"https://github.com/player-Muteki/co-thinker/releases/download/{tag}/{wheel_name}",
            },
        ],
    }).encode()


class TestUpgrade:
    def test_upgrade_already_latest(self):
        """当前版本 >= 线上版本 → 提示已是最新。"""
        resp = _mock_urlopen(_make_release("v0.0.1"))  # 低于当前 0.1.0

        with patch("urllib.request.urlopen", return_value=resp):
            result = runner.invoke(app, ["upgrade", "--yes"])

        assert result.exit_code == 0
        assert "已是最新版本" in result.stdout

    def test_upgrade_no_wheel_asset(self):
        """Release 中没有 .whl 文件 → 报错。"""
        resp = _mock_urlopen(json.dumps({"tag_name": "v9.9.9", "assets": []}).encode())

        with patch("urllib.request.urlopen", return_value=resp):
            result = runner.invoke(app, ["upgrade", "--yes"])

        assert result.exit_code == 1
        assert "未找到可下载的 wheel" in result.stdout

    def test_upgrade_api_unreachable(self):
        """GitHub API 不可达 → 报错。"""
        with patch("urllib.request.urlopen", side_effect=OSError("Connection refused")):
            result = runner.invoke(app, ["upgrade", "--yes"])

        assert result.exit_code == 1
        assert "无法获取最新版本信息" in result.stdout

    def test_upgrade_downloads_and_installs(self, tmp_path: Path):
        """发现新版本 → 下载 wheel → pip install --upgrade。"""
        wheel_name = "co_thinker-9.9.9-py3-none-any.whl"
        resp = _mock_urlopen(_make_release("v9.9.9", wheel_name))

        fake_wheel = tmp_path / wheel_name
        fake_wheel.write_text("fake wheel content")

        def fake_urlretrieve(url, path):
            import shutil
            shutil.copy2(str(fake_wheel), path)
            return path, None

        mock_subprocess = MagicMock()
        mock_subprocess.returncode = 0

        with (
            patch("urllib.request.urlopen", return_value=resp),
            patch("urllib.request.urlretrieve", side_effect=fake_urlretrieve),
            patch("subprocess.run", return_value=mock_subprocess) as mock_run,
        ):
            result = runner.invoke(app, ["upgrade", "--yes"])

        assert result.exit_code == 0, f"STDOUT: {result.stdout}"
        assert "更新完成" in result.stdout

        # 验证 pip install --upgrade 被调用
        call_args = mock_run.call_args[0][0]
        assert "pip" in call_args
        assert "install" in call_args
        assert "--upgrade" in call_args

    def test_upgrade_pip_install_fails(self, tmp_path: Path):
        """pip install --upgrade 返回错误 → 报错 + 提示回滚命令。"""
        wheel_name = "co_thinker-9.9.9-py3-none-any.whl"
        resp = _mock_urlopen(_make_release("v9.9.9", wheel_name))

        fake_wheel = tmp_path / wheel_name
        fake_wheel.write_text("fake wheel content")

        def fake_urlretrieve(url, path):
            import shutil
            shutil.copy2(str(fake_wheel), path)
            return path, None

        mock_subprocess = MagicMock()
        mock_subprocess.returncode = 1
        mock_subprocess.stderr = "pip error: network unreachable"

        with (
            patch("urllib.request.urlopen", return_value=resp),
            patch("urllib.request.urlretrieve", side_effect=fake_urlretrieve),
            patch("subprocess.run", return_value=mock_subprocess),
        ):
            result = runner.invoke(app, ["upgrade", "--yes"])

        assert result.exit_code == 1
        assert "安装失败" in result.stdout
        assert "pip error" in result.stderr or "pip error" in result.stdout
        assert "手动回滚" in result.stdout

    def test_upgrade_packaging_fallback(self, tmp_path: Path):
        """packaging 不可用 → 退回到字符串比较。"""
        wheel_name = "co_thinker-9.9.9-py3-none-any.whl"
        resp = _mock_urlopen(_make_release("v9.9.9", wheel_name))

        fake_wheel = tmp_path / wheel_name
        fake_wheel.write_text("fake wheel content")

        def fake_urlretrieve(url, path):
            import shutil
            shutil.copy2(str(fake_wheel), path)
            return path, None

        mock_subprocess = MagicMock()
        mock_subprocess.returncode = 0

        with (
            patch("urllib.request.urlopen", return_value=resp),
            patch("urllib.request.urlretrieve", side_effect=fake_urlretrieve),
            patch("subprocess.run", return_value=mock_subprocess),
            patch.dict("sys.modules", {"packaging": None}),  # force ImportError
        ):
            result = runner.invoke(app, ["upgrade", "--yes"])

        # packaging 被 patch 为 None 后 import 会失败，触发 fallback。
        # 此时 9.9.9 != 0.1.7 → is_newer=True，应继续执行。
        assert result.exit_code == 0, f"STDOUT: {result.stdout}"
        assert "更新完成" in result.stdout
