from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.agent_modes import AgentMode


@dataclass(frozen=True)
class PlannedToolCall:
    name: str
    arguments: dict[str, Any]
    reason: str


@dataclass(frozen=True)
class AgentPlan:
    goal: str
    steps: list[PlannedToolCall] = field(default_factory=list)
    summary: str = ""


class AgentPlanner:
    def plan(self, goal: str, mode: AgentMode = AgentMode.DEFAULT) -> AgentPlan:
        text = goal.casefold()
        steps: list[PlannedToolCall] = []

        if any(word in text for word in ["清空", "clear", "删除所有", "wipe"]):
            steps.append(PlannedToolCall("kb_clear_index", {}, "用户请求清空知识库索引"))
        elif any(word in text for word in ["重建", "rebuild"]):
            steps.append(PlannedToolCall("kb_rebuild_index", {}, "用户请求重建知识库索引"))
        elif any(word in text for word in ["索引", "index", "纳入"]):
            paths = self._extract_paths(goal)
            if paths:
                steps.append(PlannedToolCall("kb_index_files", {"paths": paths}, "用户请求索引指定文件"))
            else:
                steps.append(PlannedToolCall("kb_list_files", {}, "查找可纳入知识库的文件"))
        elif any(word in text for word in ["失败", "failed", "错误"]):
            steps.extend([
                PlannedToolCall("kb_get_stats", {}, "获取知识库统计"),
                PlannedToolCall("kb_list_documents", {"status": "failed"}, "列出失败文档"),
            ])
        elif any(word in text for word in ["搜索", "查找", "search"]):
            steps.append(PlannedToolCall("kb_search", {"query": goal, "top_k": 5}, "搜索知识库内容"))
        elif any(word in text for word in ["文件", "files", "未索引"]):
            steps.append(PlannedToolCall("kb_list_files", {}, "列出工作区文件"))
        else:
            steps.append(PlannedToolCall("kb_get_stats", {}, "获取知识库整体状态"))

        summary = "生成只读计划" if mode == AgentMode.PLAN else "生成执行计划"
        return AgentPlan(goal=goal, steps=steps, summary=summary)

    @staticmethod
    def _extract_paths(goal: str) -> list[str]:
        return [token for token in goal.split() if "/" in token or token.endswith((".md", ".txt", ".pdf", ".docx", ".pptx"))]
