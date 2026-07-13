from __future__ import annotations

from core.agent_events import AgentEventType
from core.agent_modes import AgentMode
from tests.conftest import make_runtime


class TestAgentWorkflow:
    def test_default_mode_executes_readonly_tool(self, tmp_path):
        runtime = make_runtime(tmp_path)

        events = list(runtime.get_agent_workflow().execute("检查知识库状态"))

        assert any(event.type == AgentEventType.TOOL_CALL_RESULT and event.tool_name == "kb_get_stats" for event in events)
        assert events[-1].type == AgentEventType.DONE

    def test_mutating_tool_requires_approval(self, tmp_path):
        runtime = make_runtime(tmp_path)

        events = list(runtime.get_agent_workflow().execute("重建索引"))

        approval = next(event for event in events if event.type == AgentEventType.APPROVAL_REQUIRED)
        assert approval.tool_name == "kb_rebuild_index"
        assert approval.approval_id.startswith("appr_")

    def test_dangerous_tool_is_denied(self, tmp_path):
        runtime = make_runtime(tmp_path)

        events = list(runtime.get_agent_workflow().execute("清空所有索引"))

        error = next(event for event in events if event.type == AgentEventType.ERROR)
        assert error.tool_name == "kb_clear_index"
        assert "denied" in error.error

    def test_plan_mode_saves_plan_and_does_not_execute_mutation(self, tmp_path):
        runtime = make_runtime(tmp_path)

        events = list(runtime.get_agent_workflow().execute("重建索引", mode=AgentMode.PLAN))

        plan = next(event for event in events if event.type == AgentEventType.PLAN_CREATED)
        approval = next(event for event in events if event.type == AgentEventType.APPROVAL_REQUIRED)
        assert plan.plan_id.startswith("plan_")
        assert approval.approval_id.startswith("preview_")
        assert not any(event.type == AgentEventType.TOOL_CALL_RESULT for event in events)

    def test_workflow_persists_approval_and_session_events(self, tmp_path):
        runtime = make_runtime(tmp_path)

        events = list(runtime.get_agent_workflow().execute("重建索引"))
        approval = next(event for event in events if event.type == AgentEventType.APPROVAL_REQUIRED)

        approvals = runtime.get_agent_workflow().list_approvals()
        sessions = runtime.get_agent_workflow().list_sessions()
        stored_events = runtime.get_agent_workflow().read_session(events[0].session_id)

        assert approvals[0].id == approval.approval_id
        assert approvals[0].status == "pending"
        assert sessions[0].status == "done"
        assert len(stored_events) == len(events)

    def test_approve_and_execute_runs_approved_tool(self, tmp_path):
        runtime = make_runtime(tmp_path)

        events = list(runtime.get_agent_workflow().execute("重建索引"))
        approval_event = next(event for event in events if event.type == AgentEventType.APPROVAL_REQUIRED)

        workflow = runtime.get_agent_workflow()
        workflow.approve(approval_event.approval_id)
        exec_events = list(workflow.execute_approved(approval_event.approval_id))

        assert any(event.type == AgentEventType.TOOL_CALL_RESULT and event.tool_name == "kb_rebuild_index" for event in exec_events)

        final_approval = next(a for a in workflow.list_approvals() if a.id == approval_event.approval_id)
        assert final_approval.status == "executed"
