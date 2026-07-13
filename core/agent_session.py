from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from uuid import uuid4

from core.agent_events import AgentEvent, utc_now
from core.agent_modes import AgentMode


@dataclass(frozen=True)
class AgentSessionMeta:
    id: str
    goal: str
    mode: str
    status: str
    created_at: str
    updated_at: str
    event_count: int = 0

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class AgentSessionStore:
    def __init__(self, co_dir: Path):
        self._sessions_dir = co_dir / "agent-sessions"
        self._sessions_dir.mkdir(parents=True, exist_ok=True)
        self._index_path = self._sessions_dir / "index.json"

    def create(self, goal: str, mode: AgentMode, session_id: str | None = None) -> AgentSessionMeta:
        session_id = session_id or f"ags_{uuid4().hex}"
        now = utc_now()
        meta = AgentSessionMeta(
            id=session_id,
            goal=goal,
            mode=mode.value,
            status="running",
            created_at=now,
            updated_at=now,
            event_count=0,
        )
        self._upsert_meta(meta)
        self._events_path(session_id).touch(exist_ok=True)
        return meta

    def append(self, session_id: str, event: AgentEvent) -> None:
        with self._events_path(session_id).open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event.to_dict(), ensure_ascii=False) + "\n")
        meta = self.get_meta(session_id)
        if meta:
            status = "done" if event.type.value == "done" else "error" if event.type.value == "error" else meta.status
            self._upsert_meta(AgentSessionMeta(
                id=meta.id,
                goal=meta.goal,
                mode=meta.mode,
                status=status,
                created_at=meta.created_at,
                updated_at=utc_now(),
                event_count=meta.event_count + 1,
            ))

    def read(self, session_id: str) -> list[dict[str, object]]:
        path = self._events_path(session_id)
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def list(self) -> list[AgentSessionMeta]:
        return [AgentSessionMeta(**item) for item in self._read_index()]

    def get_meta(self, session_id: str) -> AgentSessionMeta | None:
        for item in self._read_index():
            if item["id"] == session_id:
                return AgentSessionMeta(**item)
        return None

    def _upsert_meta(self, meta: AgentSessionMeta) -> None:
        items = [item for item in self._read_index() if item["id"] != meta.id]
        items.append(meta.to_dict())
        self._index_path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")

    def _read_index(self) -> list[dict[str, object]]:
        if not self._index_path.exists():
            return []
        return json.loads(self._index_path.read_text(encoding="utf-8"))

    def _events_path(self, session_id: str) -> Path:
        return self._sessions_dir / f"{session_id}.jsonl"
