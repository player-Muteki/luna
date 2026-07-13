from __future__ import annotations

import json
from unittest.mock import patch

from typer.testing import CliRunner

from cli import app
from core.agent_approval import AgentApproval
from core.agent_events import AgentEvent, AgentEventType
from core.agent_session import AgentSessionMeta

runner = CliRunner()


class _FakeAgentWorkflow:
    def execute(self, goal, *, mode, approval_mode, generate_response=False):
        yield AgentEvent(type=AgentEventType.MESSAGE, session_id="ags_1", message=f"goal: {goal}")
        yield AgentEvent(type=AgentEventType.DONE, session_id="ags_1", message="done")

    def list_plans(self):
        return []

    def list_approvals(self):
        return [AgentApproval(
            id="appr_1",
            session_id="ags_1",
            tool_name="kb_rebuild_index",
            arguments={},
            category="mutating",
            reason="changes index",
            status="pending",
            created_at="now",
        )]

    def approve(self, approval_id):
        return AgentApproval(
            id=approval_id,
            session_id="ags_1",
            tool_name="kb_rebuild_index",
            arguments={},
            category="mutating",
            reason="changes index",
            status="approved",
            created_at="now",
            decided_at="later",
        )

    def execute_approved(self, approval_id):
        yield AgentEvent(type=AgentEventType.TOOL_CALL_START, session_id="ags_1", tool_name="kb_rebuild_index")
        yield AgentEvent(type=AgentEventType.TOOL_CALL_RESULT, session_id="ags_1", tool_name="kb_rebuild_index", body={"status": "rebuilt"})
        yield AgentEvent(type=AgentEventType.DONE, session_id="ags_1", message="done")

    def reject(self, approval_id):
        return AgentApproval(
            id=approval_id,
            session_id="ags_1",
            tool_name="kb_rebuild_index",
            arguments={},
            category="mutating",
            reason="changes index",
            status="rejected",
            created_at="now",
            decided_at="later",
        )

    def list_sessions(self):
        return [AgentSessionMeta(
            id="ags_1",
            goal="检查知识库",
            mode="default",
            status="done",
            created_at="now",
            updated_at="later",
            event_count=2,
        )]

    def read_session(self, session_id):
        return [{"type": "message", "session_id": session_id, "message": "hello"}]


class _FakeWorkspaceRuntime:
    def get_agent_workflow(self):
        return _FakeAgentWorkflow()


class TestCliAgent:
    def test_agent_command_prints_events(self):
        with patch("cli._setup_project_context", return_value=_FakeWorkspaceRuntime()):
            result = runner.invoke(app, ["agent", "run", "检查知识库状态"])

        assert result.exit_code == 0
        assert "goal: 检查知识库状态" in result.stdout
        assert "done" in result.stdout

    def test_agent_command_supports_jsonl(self):
        with patch("cli._setup_project_context", return_value=_FakeWorkspaceRuntime()):
            result = runner.invoke(app, ["agent", "run", "检查知识库状态", "--json"])

        assert result.exit_code == 0
        lines = [json.loads(line) for line in result.stdout.splitlines()]
        assert lines[0]["type"] == "message"
        assert lines[-1]["type"] == "done"

    def test_agent_plans_command_prints_empty_list(self):
        with patch("cli._setup_project_context", return_value=_FakeWorkspaceRuntime()):
            result = runner.invoke(app, ["agent", "plans"])

        assert result.exit_code == 0

    def test_agent_approvals_command_prints_items(self):
        with patch("cli._setup_project_context", return_value=_FakeWorkspaceRuntime()):
            result = runner.invoke(app, ["agent", "approvals"])

        assert result.exit_code == 0
        assert "appr_1" in result.stdout
        assert "kb_rebuild_index" in result.stdout

    def test_agent_approve_and_reject_commands(self):
        with patch("cli._setup_project_context", return_value=_FakeWorkspaceRuntime()):
            approved = runner.invoke(app, ["agent", "approve", "appr_1"])
            rejected = runner.invoke(app, ["agent", "reject", "appr_1"])

        assert approved.exit_code == 0
        assert "[approved] appr_1" in approved.stdout
        assert rejected.exit_code == 0
        assert "[rejected] appr_1" in rejected.stdout

    def test_agent_sessions_and_show_commands(self):
        with patch("cli._setup_project_context", return_value=_FakeWorkspaceRuntime()):
            sessions = runner.invoke(app, ["agent", "sessions"])
            show = runner.invoke(app, ["agent", "show", "ags_1"])

        assert sessions.exit_code == 0
        assert "ags_1" in sessions.stdout
        assert show.exit_code == 0
        assert "hello" in show.stdout
