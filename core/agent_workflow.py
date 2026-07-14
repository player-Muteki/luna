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
        generate_response: bool = False,
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

        tool_results: list[AgentEvent] = []
        for step in plan.steps:
            for event in self._executor.execute(
                step,
                session_id=session.id,
                mode=mode,
                approval_mode=approval_mode,
            ):
                yield from self._emit(event)
                if event.type == AgentEventType.TOOL_CALL_RESULT:
                    tool_results.append(event)

        if generate_response and tool_results and mode != AgentMode.PLAN:
            response = self._generate_response(goal, tool_results)
            if response:
                yield from self._emit(AgentEvent(
                    type=AgentEventType.MESSAGE,
                    session_id=session.id,
                    message=response,
                ))

        yield from self._emit(AgentEvent(
            type=AgentEventType.DONE,
            session_id=session.id,
            message="Agent 处理完成。" if mode != AgentMode.PLAN else "计划生成完成。",
        ))

    def _generate_response(self, goal: str, tool_results: list[AgentEvent]) -> str | None:
        llm = getattr(self._runtime, "llm", None)
        if llm is None:
            return None

        prompt_lines = [
            "你是一个知识库管理助手。请根据用户目标和工具执行结果，用简洁的自然语言总结发生了什么。",
            "",
            f"用户目标：{goal}",
            "",
            "工具执行结果：",
        ]
        for event in tool_results:
            body = event.body or {}
            if event.tool_name == "kb_get_stats":
                prompt_lines.append(f"- 知识库统计：{body.get('document_count', 0)} 个文档，{body.get('chunk_count', 0)} 个片段")
            elif event.tool_name == "kb_search":
                results = body.get("results", [])
                prompt_lines.append(f"- 搜索到 {len(results)} 个相关结果")
            elif event.tool_name == "kb_index_files":
                prompt_lines.append(f"- 已索引 {body.get('indexed_files', 0)} 个文件，{body.get('total_chunks', 0)} 个片段")
            elif event.tool_name == "kb_rebuild_index":
                prompt_lines.append(f"- 重建索引完成：{body.get('indexed_files', 0)} 个文件，{body.get('failed_files', 0)} 个失败")
            elif event.tool_name == "kb_list_files":
                files = body.get("files", [])
                indexed = sum(1 for f in files if f.get("is_indexed"))
                prompt_lines.append(f"- 工作区共 {len(files)} 个文件，{indexed} 个已索引")
            elif event.tool_name == "kb_list_documents":
                docs = body.get("documents", [])
                prompt_lines.append(f"- 共 {len(docs)} 个文档")
            elif event.tool_name == "kb_delete_document":
                prompt_lines.append(f"- 文档已删除：{body.get('document_id', 'unknown')}")
            elif event.tool_name == "kb_update_tags":
                prompt_lines.append(f"- 标签已更新")
            else:
                prompt_lines.append(f"- {event.tool_name} 执行完成")

        prompt_lines.extend([
            "",
            "请用简洁的语言总结结果，不要超过 200 字。",
        ])

        try:
            response = llm.chat.completions.create(
                model=self._get_llm_model_name(),
                messages=[
                    {"role": "system", "content": "你是一个知识库管理助手，用简洁的中文总结工具执行结果。"},
                    {"role": "user", "content": "\n".join(prompt_lines)},
                ],
                max_tokens=500,
                temperature=0.3,
            )
            return response.choices[0].message.content
        except Exception:
            return None

    @staticmethod
    def _get_llm_model_name() -> str:
        from core.project import _load_global_config, _global_model_name
        cfg = _load_global_config()
        return _global_model_name(cfg) or "deepseek-chat"

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
