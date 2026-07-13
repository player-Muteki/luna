from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from uuid import uuid4

from core.agent_events import utc_now
from core.agent_planner import AgentPlan


@dataclass(frozen=True)
class StoredAgentPlan:
    id: str
    goal: str
    steps: list[dict[str, object]]
    status: str
    created_at: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class AgentPlanStore:
    def __init__(self, co_dir: Path):
        self._plans_dir = co_dir / "plans"
        self._plans_dir.mkdir(parents=True, exist_ok=True)

    def create(self, plan: AgentPlan) -> StoredAgentPlan:
        stored = StoredAgentPlan(
            id=f"plan_{uuid4().hex}",
            goal=plan.goal,
            steps=[asdict(step) for step in plan.steps],
            status="pending",
            created_at=utc_now(),
        )
        self._path(stored.id).write_text(
            json.dumps(stored.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return stored

    def get(self, plan_id: str) -> StoredAgentPlan | None:
        path = self._path(plan_id)
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return StoredAgentPlan(**data)

    def list(self) -> list[StoredAgentPlan]:
        plans = []
        for path in sorted(self._plans_dir.glob("plan_*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            plans.append(StoredAgentPlan(**data))
        return plans

    def _path(self, plan_id: str) -> Path:
        return self._plans_dir / f"{plan_id}.json"
