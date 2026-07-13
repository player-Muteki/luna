from __future__ import annotations

from enum import Enum


class AgentMode(str, Enum):
    DEFAULT = "default"
    PLAN = "plan"
    GOAL = "goal"


class ApprovalMode(str, Enum):
    ASK = "ask"
    AUTO_READONLY = "auto_readonly"
    AUTO_SAFE_MUTATION = "auto_safe_mutation"
