"""
ChatWorkflow 测试 — 纯 RAG 对话流程。

覆盖：
  - 有检索结果：retrieval_done → (chunk*) → done
  - 无检索结果：done (zero references)
  - 会话历史传递
  - 用户/助手消息持久化
  - 异常处理
"""

from __future__ import annotations

from pathlib import Path

from core.chat_workflow import ChatWorkflow, WorkflowEvent

from tests.conftest import make_runtime, FakeLLM

def _add_doc(tmp_path: Path, name: str, content: str) -> None:
    """在 tmp_path 下创建一个文档并索引。"""
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    runtime = make_runtime(tmp_path)
    runtime.ingest_engine.add_files([path])


class TestChatWorkflow:
    def test_normal_path_yields_events(self, tmp_path: Path) -> None:
        """有检索结果 → retrieval_done + chunk + done。"""
        _add_doc(tmp_path, "doc.md", "Hybrid retrieval combines vector with BM25.")
        runtime = make_runtime(tmp_path)
        workflow = ChatWorkflow(runtime)

        events = list(workflow.execute("retrieval", session_id=None))

        types = [e.type for e in events]
        assert "retrieval_done" in types
        assert types[-1] == "done"
        # There should be at least one chunk
        chunks = [e for e in events if e.type == "chunk"]
        assert len(chunks) >= 1
        # Done event should have references
        done = [e for e in events if e.type == "done"][0]
        assert len(done.data.get("references", [])) > 0

    def test_no_results_yields_empty_done(self, tmp_path: Path) -> None:
        """无检索结果 → done 事件（零 references）。"""
        # Don't add any documents — empty index
        runtime = make_runtime(tmp_path)
        workflow = ChatWorkflow(runtime)

        events = list(workflow.execute("nonexistent-token"))

        assert len(events) == 1
        assert events[0].type == "done"
        assert events[0].data.get("references") == []
        assert events[0].data.get("confidence") == "none"

    def test_retrieval_done_contains_details(self, tmp_path: Path) -> None:
        """retrieval_done 事件包含模式和候选数。"""
        _add_doc(tmp_path, "doc.md", "Retrieval content for testing.")
        runtime = make_runtime(tmp_path)
        workflow = ChatWorkflow(runtime)

        events = list(workflow.execute("retrieval"))

        rd = [e for e in events if e.type == "retrieval_done"]
        assert len(rd) == 1
        assert "mode" in rd[0].data
        assert rd[0].data["total_candidates"] > 0

    def test_persists_user_and_assistant_messages(self, tmp_path: Path) -> None:
        """workflow 执行后会持久化用户和助手消息。"""
        _add_doc(tmp_path, "doc.md", "Generator builds answers from context.")
        runtime = make_runtime(tmp_path)
        session_id = runtime.chat_engine.create_conversation().conversation_id
        workflow = ChatWorkflow(runtime)

        list(workflow.execute("generator", session_id=session_id))

        conv = runtime.chat_engine.conversations.get(session_id)
        assert conv is not None
        roles = [msg.role for msg in conv.messages]
        assert "user" in roles
        assert "assistant" in roles

    def test_no_session_id_no_crash(self, tmp_path: Path) -> None:
        """没有 session_id 时不会崩溃（chat_engine.current_id 为 None）。"""
        _add_doc(tmp_path, "doc.md", "Some content.")
        runtime = make_runtime(tmp_path)
        workflow = ChatWorkflow(runtime)

        events = list(workflow.execute("content", session_id=None))

        types = [e.type for e in events]
        assert types[-1] == "done"

    def test_done_event_contains_references(self, tmp_path: Path) -> None:
        """done event 包含 references 和 confidence。"""
        _add_doc(tmp_path, "doc.md", "This is some content for retrieval.")
        runtime = make_runtime(tmp_path)
        workflow = ChatWorkflow(runtime)

        events = list(workflow.execute("content"))
        done = [e for e in events if e.type == "done"][0]

        assert "references" in done.data
        assert "confidence" in done.data
        assert done.data["confidence"] in ("high", "medium", "low", "none")
