from __future__ import annotations

import itertools
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from core.agent_tools import KnowledgeToolset


class RustAgentRuntime:
    """通过 Rust stdio runtime 做 tool policy 检查。

    当 Rust 二进制不可用时自动回退到纯 Python 执行（跳过策略检查）。
    """

    def __init__(
        self,
        toolset: "KnowledgeToolset | None" = None,
        *,
        repo_root: Path | None = None,
        timeout_seconds: float = 10.0,
    ):
        self._toolset = toolset
        self._repo_root = (repo_root or Path(__file__).resolve().parent.parent).resolve()
        self._timeout_seconds = timeout_seconds
        self._request_ids = itertools.count(1)
        self._available: bool | None = None  # lazy check

    @property
    def available(self) -> bool:
        if self._available is None:
            try:
                self._command()
                self._available = True
            except RuntimeError:
                self._available = False
        return self._available

    def check_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if not self.available:
            return {"ok": True, "status": "allowed", "tool_name": name}
        return self._rpc("tools/check", {"name": name, "arguments": arguments})

    def call_tool(self, name: str, arguments: dict[str, Any], *, skip_policy: bool = False) -> dict[str, Any]:
        if not skip_policy:
            policy = self.check_tool(name, arguments)
            if policy.get("status") != "allowed":
                return policy
        if self._toolset is None:
            raise RuntimeError("KnowledgeToolset is not configured")

        start_event = {
            "type": "tool_call_start",
            "tool_name": name,
            "status": "allowed",
            "message": None,
        }
        try:
            body = self._toolset.call(name, arguments)
        except Exception as exc:
            message = str(exc)
            return {
                "ok": False,
                "status": "error",
                "tool_name": name,
                "reason": message,
                "body": None,
                "events": [
                    start_event,
                    {
                        "type": "error",
                        "tool_name": name,
                        "status": "error",
                        "message": message,
                    },
                ],
            }

        return {
            "ok": True,
            "status": "completed",
            "tool_name": name,
            "body": body,
            "events": [
                start_event,
                {
                    "type": "tool_call_result",
                    "tool_name": name,
                    "status": "completed",
                    "message": None,
                },
            ],
        }

    def list_tools(self) -> dict[str, Any]:
        return self._rpc("tools/list", {})

    def healthz(self) -> dict[str, Any]:
        return self._rpc("healthz", {})

    def _rpc(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        request = {
            "jsonrpc": "2.0",
            "id": next(self._request_ids),
            "method": method,
            "params": params,
        }
        payload = json.dumps(request, ensure_ascii=False) + "\n"

        try:
            result = subprocess.run(
                self._command(),
                input=payload,
                capture_output=True,
                text=True,
                cwd=str(self._repo_root),
                timeout=self._timeout_seconds,
                check=False,
            )
        except FileNotFoundError as exc:
            raise RuntimeError("Rust agent runtime is unavailable") from exc
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("Rust agent runtime timed out") from exc

        if result.returncode != 0:
            stderr = (result.stderr or "").strip()
            raise RuntimeError(f"Rust agent runtime failed: {stderr or f'exit code {result.returncode}'}")

        response_line = self._extract_response_line(result.stdout)
        try:
            response = json.loads(response_line)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Rust agent runtime returned invalid JSON") from exc

        if "error" in response:
            message = response["error"].get("message", "Unknown JSON-RPC error")
            raise RuntimeError(f"Rust agent runtime error: {message}")

        result_payload = response.get("result")
        if not isinstance(result_payload, dict):
            raise RuntimeError("Rust agent runtime returned invalid result payload")
        return result_payload

    def _command(self) -> list[str]:
        configured = os.environ.get("LUNA_AGENT_RUNTIME_BIN")
        if configured:
            return [configured]

        binary_name = "luna-agent-runtime.exe" if os.name == "nt" else "luna-agent-runtime"
        candidate = self._repo_root / "target" / "debug" / binary_name
        if candidate.exists():
            return [str(candidate)]

        on_path = shutil.which(binary_name)
        if on_path:
            return [on_path]

        cargo = shutil.which("cargo")
        if cargo:
            return [cargo, "run", "--quiet", "--package", "luna-agent-runtime", "--"]

        raise RuntimeError("Neither cargo nor a built luna-agent-runtime binary is available")

    @staticmethod
    def _extract_response_line(stdout: str) -> str:
        for line in reversed(stdout.splitlines()):
            line = line.strip()
            if line:
                return line
        raise RuntimeError("Rust agent runtime returned no output")
