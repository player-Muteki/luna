from __future__ import annotations

from typing import Iterable
from uuid import uuid4

from core.agent_approval import AgentApprovalStore
from core.agent_contracts import get_tool_contract
from core.agent_events import AgentEvent, AgentEventType
from core.agent_modes import AgentMode, ApprovalMode
from core.agent_planner import PlannedToolCall


class AgentToolExecutor:
    def __init__(self, runtime, approval_store: AgentApprovalStore | None = None):
        self._runtime = runtime
        self._approval_store = approval_store or AgentApprovalStore(runtime.co_dir)

    def execute(
        self,
        call: PlannedToolCall,
        *,
        session_id: str,
        mode: AgentMode,
        approval_mode: ApprovalMode,
        approved: bool = False,
    ) -> Iterable[AgentEvent]:
        contract = get_tool_contract(call.name)
        if contract is None:
            yield AgentEvent(
                type=AgentEventType.ERROR,
                session_id=session_id,
                tool_name=call.name,
                error=f"Unknown tool: {call.name}",
            )
            return

        if mode == AgentMode.PLAN and contract.category != "read_only":
            yield AgentEvent(
                type=AgentEventType.APPROVAL_REQUIRED,
                session_id=session_id,
                tool_name=call.name,
                arguments=call.arguments,
                approval_id=f"preview_{uuid4().hex}",
                message=f"Plan includes {call.name}, but plan mode will not execute mutating tools.",
            )
            return

        if contract.category == "dangerous":
            yield AgentEvent(
                type=AgentEventType.ERROR,
                session_id=session_id,
                tool_name=call.name,
                arguments=call.arguments,
                error=f"Tool {call.name} is denied by policy.",
            )
            return

        if not approved and contract.category == "mutating" and not self._auto_allows(call.name, approval_mode):
            reason = f"Tool {call.name} changes the knowledge base."
            approval = self._approval_store.create(
                session_id=session_id,
                tool_name=call.name,
                arguments=call.arguments,
                reason=reason,
            )
            yield AgentEvent(
                type=AgentEventType.APPROVAL_REQUIRED,
                session_id=session_id,
                tool_name=call.name,
                arguments=call.arguments,
                approval_id=approval.id,
                message=reason,
            )
            return

        yield AgentEvent(
            type=AgentEventType.TOOL_CALL_START,
            session_id=session_id,
            tool_name=call.name,
            arguments=call.arguments,
            message=call.reason,
        )
        response = self._runtime.get_agent_runtime().call_tool(call.name, call.arguments, skip_policy=approved)
        status = response.get("status")
        if status == "completed":
            yield AgentEvent(
                type=AgentEventType.TOOL_CALL_RESULT,
                session_id=session_id,
                tool_name=call.name,
                body=response.get("body") or {},
            )
            return
        if status == "approval_required":
            reason = response.get("reason") or f"Tool {call.name} changes the knowledge base."
            approval = self._approval_store.create(
                session_id=session_id,
                tool_name=call.name,
                arguments=call.arguments,
                reason=reason,
            )
            yield AgentEvent(
                type=AgentEventType.APPROVAL_REQUIRED,
                session_id=session_id,
                tool_name=call.name,
                arguments=call.arguments,
                approval_id=approval.id,
                message=reason,
            )
            return
        yield AgentEvent(
            type=AgentEventType.ERROR,
            session_id=session_id,
            tool_name=call.name,
            error=response.get("reason") or f"Tool {call.name} failed with status {status}",
        )

    @staticmethod
    def _auto_allows(name: str, approval_mode: ApprovalMode) -> bool:
        return approval_mode == ApprovalMode.AUTO_SAFE_MUTATION and name in {"kb_index_files", "kb_update_tags"}
