from __future__ import annotations

import pytest

from core.agent_approval import AgentApprovalStore


def test_approval_store_create_approve_reject(tmp_path):
    store = AgentApprovalStore(tmp_path / ".luna")
    approval = store.create(
        session_id="ags_1",
        tool_name="kb_rebuild_index",
        arguments={},
        reason="changes index",
    )

    assert approval.status == "pending"
    assert approval.category == "mutating"
    assert store.get(approval.id).tool_name == "kb_rebuild_index"

    approved = store.approve(approval.id)
    assert approved.status == "approved"

    with pytest.raises(ValueError, match="not pending"):
        store.reject(approval.id)


def test_approval_store_reject(tmp_path):
    store = AgentApprovalStore(tmp_path / ".luna")
    approval = store.create(
        session_id="ags_1",
        tool_name="kb_rebuild_index",
        arguments={},
        reason="changes index",
    )

    rejected = store.reject(approval.id)

    assert rejected.status == "rejected"
    assert store.list()[0].id == approval.id
