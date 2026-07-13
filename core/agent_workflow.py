from __future__ import annotations

from typing import Iterable

from core.agent_approval import AgentApproval, AgentApprovalStore
from core.agent_contracts import get_tool_contract
from core.agent_events import AgentEvent, AgentEventType
from core.agent_executor import AgentToolExecutor
from core.agent_modes import AgentMode, ApprovalMode
from core.agent_plan_store import AgentPlanStore
from core.agent_planner import AgentPlanner, PlannedToolCall
from core.agent_session import AgentSessionStore


class AgentWorkflow:
    def __init__(
        self,
        runtime,
        *,
        planner: AgentPlanner | None = None,
        executor: AgentToolExecutor | None = None,
        plan_store: AgentPlanStore | None = None,
        approval_store: AgentApprovalStore | None = None,
        session_store: AgentSessionStore | None = None,
    ):
        self._runtime = runtime
        self._planner = planner or AgentPlanner()
        self._approval_store = approval_store or AgentApprovalStore(runtime.co_dir)
        self._session_store = session_store or AgentSessionStore(runtime.co_dir)
        self._executor = executor or AgentToolExecutor(runtime, self._approval_store)
        self._plan_store = plan_store or AgentPlanStore(runtime.co_dir)

    def execute(
        self,
        goal: str,
        *,
        session_id: str | None = None,
        mode: AgentMode = AgentMode.DEFAULT,
        approval_mode: ApprovalMode = ApprovalMode.ASK,
    ) -> Iterable[AgentEvent]:
        session = self._session_store.create(goal, mode, session_id)
        yield from self._emit(AgentEvent(
            type=AgentEventType.MESSAGE,
            session_id=session.id,
            message=f"开始处理目标：{goal}",
        ))

        plan = self._planner.plan(goal, mode)
        if mode == AgentMode.PLAN:
            stored = self._plan_store.create(plan)
            yield from self._emit(AgentEvent(
                type=AgentEventType.PLAN_CREATED,
                session_id=session.id,
                plan_id=stored.id,
                body=stored.to_dict(),
                message="已生成计划，未执行变更操作。",
            ))

        for step in plan.steps:
            for event in self._executor.execute(
                step,
                session_id=session.id,
                mode=mode,
                approval_mode=approval_mode,
            ):
                yield from self._emit(event)

        yield from self._emit(AgentEvent(
            type=AgentEventType.DONE,
            session_id=session.id,
            message="Agent 处理完成。" if mode != AgentMode.PLAN else "计划生成完成。",
        ))

    def _emit(self, event: AgentEvent) -> Iterable[AgentEvent]:
        self._session_store.append(event.session_id, event)
        yield event

    def list_plans(self):
        return self._plan_store.list()

    def list_approvals(self):
        return self._approval_store.list()

    def approve(self, approval_id: str):
        return self._approval_store.approve(approval_id)

    def execute_approved(self, approval_id: str) -> Iterable[AgentEvent]:
        approval = self._approval_store.get(approval_id)
        if approval is None:
            yield AgentEvent(
                type=AgentEventType.ERROR,
                session_id="",
                error=f"Approval not found: {approval_id}",
            )
            return
        if approval.status != "approved":
            yield AgentEvent(
                type=AgentEventType.ERROR,
                session_id=approval.session_id,
                error=f"Approval {approval_id} is not approved (status={approval.status})",
            )
            return

        contract = get_tool_contract(approval.tool_name)
        if contract is None:
            yield AgentEvent(
                type=AgentEventType.ERROR,
                session_id=approval.session_id,
                error=f"Cannot execute approved tool: unknown tool {approval.tool_name}",
            )
            return

        call = PlannedToolCall(approval.tool_name, approval.arguments, "approved tool execution")
        for event in self._executor.execute(
            call,
            session_id=approval.session_id,
            mode=AgentMode.DEFAULT,
            approval_mode=ApprovalMode.ASK,
            approved=True,
        ):
            yield from self._emit(event)
            if event.type == AgentEventType.TOOL_CALL_RESULT:
                self._approval_store.mark_executed(approval_id)

    def reject(self, approval_id: str):
        return self._approval_store.reject(approval_id)

    def list_sessions(self):
        return self._session_store.list()

    def read_session(self, session_id: str):
        return self._session_store.read(session_id)
