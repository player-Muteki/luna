from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from core.agent_contracts import get_tool_contract
from core.agent_events import utc_now


@dataclass(frozen=True)
class AgentApproval:
    id: str
    session_id: str
    tool_name: str
    arguments: dict[str, Any]
    category: str
    reason: str
    status: str
    created_at: str
    decided_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AgentApprovalStore:
    def __init__(self, co_dir: Path):
        self._approvals_dir = co_dir / "approvals"
        self._approvals_dir.mkdir(parents=True, exist_ok=True)

    def create(
        self,
        *,
        session_id: str,
        tool_name: str,
        arguments: dict[str, Any],
        reason: str,
    ) -> AgentApproval:
        contract = get_tool_contract(tool_name)
        category = contract.category if contract else "unknown"
        approval = AgentApproval(
            id=f"appr_{uuid4().hex}",
            session_id=session_id,
            tool_name=tool_name,
            arguments=arguments,
            category=category,
            reason=reason,
            status="pending",
            created_at=utc_now(),
        )
        self._write(approval)
        return approval

    def get(self, approval_id: str) -> AgentApproval | None:
        path = self._path(approval_id)
        if not path.exists():
            return None
        return AgentApproval(**json.loads(path.read_text(encoding="utf-8")))

    def list(self) -> list[AgentApproval]:
        approvals = []
        for path in sorted(self._approvals_dir.glob("appr_*.json")):
            approvals.append(AgentApproval(**json.loads(path.read_text(encoding="utf-8"))))
        return approvals

    def approve(self, approval_id: str) -> AgentApproval:
        approval = self._require_pending(approval_id)
        approved = AgentApproval(**{**approval.to_dict(), "status": "approved", "decided_at": utc_now()})
        self._write(approved)
        return approved

    def reject(self, approval_id: str) -> AgentApproval:
        approval = self._require_pending(approval_id)
        rejected = AgentApproval(**{**approval.to_dict(), "status": "rejected", "decided_at": utc_now()})
        self._write(rejected)
        return rejected

    def mark_executed(self, approval_id: str) -> AgentApproval:
        approval = self.get(approval_id)
        if approval is None:
            raise ValueError(f"Approval not found: {approval_id}")
        executed = AgentApproval(**{**approval.to_dict(), "status": "executed", "decided_at": approval.decided_at or utc_now()})
        self._write(executed)
        return executed

    def _require_pending(self, approval_id: str) -> AgentApproval:
        approval = self.get(approval_id)
        if approval is None:
            raise ValueError(f"Approval not found: {approval_id}")
        if approval.status != "pending":
            raise ValueError(f"Approval is not pending: {approval_id}")
        return approval

    def _write(self, approval: AgentApproval) -> None:
        self._path(approval.id).write_text(
            json.dumps(approval.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _path(self, approval_id: str) -> Path:
        return self._approvals_dir / f"{approval_id}.json"
