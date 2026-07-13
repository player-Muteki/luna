from __future__ import annotations

from core.agent_events import AgentEvent, AgentEventType


def test_agent_event_serializes_enum_and_omits_none():
    event = AgentEvent(
        type=AgentEventType.TOOL_CALL_RESULT,
        session_id="ags_1",
        tool_name="kb_get_stats",
        body={"document_count": 1},
    )

    payload = event.to_dict()

    assert payload["type"] == "tool_call_result"
    assert payload["session_id"] == "ags_1"
    assert payload["body"] == {"document_count": 1}
    assert "error" not in payload
