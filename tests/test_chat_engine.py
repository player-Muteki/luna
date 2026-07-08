from __future__ import annotations

import json
from pathlib import Path

from core.chat_engine import ChatEngine


def test_create_conversation_sets_current_id(tmp_path: Path) -> None:
    engine = ChatEngine(tmp_path / "chat_history.json")

    conversation = engine.create_conversation("测试会话")

    assert engine.current_id == conversation.conversation_id
    assert engine.current_conversation.title == "测试会话"


def test_add_messages_and_history_truncation(tmp_path: Path) -> None:
    engine = ChatEngine(tmp_path / "chat_history.json", max_history_turns=2)
    for i in range(3):
        engine.add_user_message(f"user-{i}")
        engine.add_assistant_message(f"assistant-{i}")

    history = engine.get_history()

    assert len(history) == 4
    assert history[0]["content"] == "user-1"
    assert history[-1]["content"] == "assistant-2"


def test_persistence_restores_messages(tmp_path: Path) -> None:
    storage = tmp_path / "chat_history.json"
    engine = ChatEngine(storage)
    engine.add_user_message("什么是 RAG？")
    engine.add_assistant_message("RAG 是检索增强生成。", confidence="high")

    restored = ChatEngine(storage)

    assert restored.current_conversation.messages[0].content == "什么是 RAG？"
    assert restored.current_conversation.messages[1].metadata["confidence"] == "high"


def test_delete_current_conversation_keeps_valid_current_id(tmp_path: Path) -> None:
    engine = ChatEngine(tmp_path / "chat_history.json")
    first = engine.current_conversation.conversation_id
    second = engine.create_conversation("第二个")

    engine.delete_conversation(second.conversation_id)

    assert engine.current_id == first
    assert engine.current_conversation.conversation_id == first


def test_corrupt_json_is_backed_up_and_reinitialized(tmp_path: Path) -> None:
    storage = tmp_path / "chat_history.json"
    storage.write_text("{broken json", encoding="utf-8")

    engine = ChatEngine(storage)

    assert engine.current_conversation.title == "新对话"
    assert storage.with_suffix(".json.broken").exists()


def test_auto_title_uses_first_user_message(tmp_path: Path) -> None:
    engine = ChatEngine(tmp_path / "chat_history.json")

    engine.add_user_message("这是一个很长的问题标题，用来验证自动标题逻辑是否生效")

    assert engine.current_conversation.title.startswith("这是一个很长的问题标题")


def test_list_conversations_exposes_preview_and_current_flag(tmp_path: Path) -> None:
    engine = ChatEngine(tmp_path / "chat_history.json")
    engine.add_user_message("第一个问题")
    second = engine.create_conversation("第二个")
    engine.add_user_message("第二个问题")

    items = engine.list_conversations()

    assert items[0]["id"] == second.conversation_id
    assert items[0]["is_current"] is True
    assert items[0]["last_message_preview"] == "第二个问题"
