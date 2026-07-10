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


def test_batch_save_no_data_loss(tmp_path: Path) -> None:
    """使用 save=False 批量添加消息后，只有最终 save() 才落盘。"""
    storage = tmp_path / "chat_history.json"
    engine = ChatEngine(storage)

    engine.add_user_message("用户问题", save=False)
    engine.add_assistant_message("助手回答", save=False)

    # save=False 期间的消息不应出现在磁盘上
    # 注意：ChatEngine 初始化时不再自动创建文件，只有 save() 才写入
    restored = ChatEngine(storage)
    assert len(restored.current_conversation.messages) == 0, "save=False 的消息不应落盘"

    # 手动保存后应有数据
    engine.save()
    restored2 = ChatEngine(storage)
    assert len(restored2.current_conversation.messages) == 2
    assert restored2.current_conversation.messages[0].content == "用户问题"
    assert restored2.current_conversation.messages[1].content == "助手回答"


def test_batch_save_prevents_orphaned_message(tmp_path: Path) -> None:
    """模拟中途崩溃场景：只执行了 add_user_message(save=False)，未执行
    add_assistant_message → 磁盘上不应有孤立消息（save() 未被调用）。"""
    storage = tmp_path / "chat_history.json"
    engine = ChatEngine(storage)

    engine.add_user_message("用户问题", save=False)

    # 模拟崩溃：没有调用 add_assistant_message 和 save()
    # 重新启动引擎后应只有初始空会话
    restored = ChatEngine(storage)
    assert len(restored.current_conversation.messages) == 0
