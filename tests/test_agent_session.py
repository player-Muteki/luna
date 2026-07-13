from __future__ import annotations

from core.agent_events import AgentEvent, AgentEventType
from core.agent_modes import AgentMode
from core.agent_session import AgentSessionStore


def test_session_store_create_append_read_and_list(tmp_path):
    store = AgentSessionStore(tmp_path / ".luna")
    session = store.create("检查知识库", AgentMode.DEFAULT, session_id="ags_1")

    store.append("ags_1", AgentEvent(
        type=AgentEventType.MESSAGE,
        session_id="ags_1",
        message="hello",
    ))
    store.append("ags_1", AgentEvent(
        type=AgentEventType.DONE,
        session_id="ags_1",
        message="done",
    ))

    events = store.read("ags_1")
    sessions = store.list()

    assert session.id == "ags_1"
    assert len(events) == 2
    assert events[0]["message"] == "hello"
    assert sessions[0].status == "done"
    assert sessions[0].event_count == 2
