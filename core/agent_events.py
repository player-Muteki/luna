from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class AgentEventType(str, Enum):
    MESSAGE = "message"
    TOOL_CALL_START = "tool_call_start"
    TOOL_CALL_RESULT = "tool_call_result"
    APPROVAL_REQUIRED = "approval_required"
    PLAN_CREATED = "plan_created"
    ERROR = "error"
    DONE = "done"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class AgentEvent:
    type: AgentEventType
    session_id: str
    message: str | None = None
    tool_name: str | None = None
    arguments: dict[str, Any] | None = None
    body: dict[str, Any] | None = None
    approval_id: str | None = None
    plan_id: str | None = None
    error: str | None = None
    created_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["type"] = self.type.value
        return {key: value for key, value in payload.items() if value is not None}
