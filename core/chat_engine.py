from __future__ import annotations

import json
import os
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Message:
    role: str
    content: str
    message_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    created_at: str = field(default_factory=utc_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_llm_message(self) -> dict[str, str]:
        return {"role": self.role, "content": self.content}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Message":
        return cls(
            role=data["role"],
            content=data["content"],
            message_id=data.get("message_id", uuid.uuid4().hex),
            created_at=data.get("created_at", utc_now_iso()),
            metadata=data.get("metadata", {}),
        )


@dataclass
class Conversation:
    conversation_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    title: str = "新对话"
    messages: list[Message] = field(default_factory=list)
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_message(self, role: str, content: str, **metadata) -> Message:
        if role not in {"user", "assistant", "system"}:
            raise ValueError(f"Invalid role: {role}")
        message = Message(role=role, content=content, metadata=metadata)
        self.messages.append(message)
        self.updated_at = utc_now_iso()
        if self.title == "新对话" and role == "user":
            self.title = auto_title_from_text(content)
        return message

    def get_recent_messages(self, max_turns: int) -> list[Message]:
        if max_turns <= 0:
            return []
        return self.messages[-max_turns * 2 :]

    def to_llm_history(self, max_turns: int) -> list[dict[str, str]]:
        return [message.to_llm_message() for message in self.get_recent_messages(max_turns)]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Conversation":
        return cls(
            conversation_id=data["conversation_id"],
            title=data.get("title", "新对话"),
            messages=[Message.from_dict(item) for item in data.get("messages", [])],
            created_at=data.get("created_at", utc_now_iso()),
            updated_at=data.get("updated_at", utc_now_iso()),
            metadata=data.get("metadata", {}),
        )


class ChatEngine:
    def __init__(self, storage_path: str | Path, max_history_turns: int = 10):
        self.storage_path = Path(storage_path)
        self.max_history_turns = max_history_turns
        self.current_id: str | None = None
        self.conversations: dict[str, Conversation] = {}
        self._lock = threading.RLock()
        self.load()

    @property
    def current_conversation(self) -> Conversation:
        if self.current_id is None or self.current_id not in self.conversations:
            return self.create_conversation()
        return self.conversations[self.current_id]

    def create_conversation(self, title: str = "新对话", **metadata) -> Conversation:
        with self._lock:
            conversation = Conversation(title=title, metadata=metadata)
            self.conversations[conversation.conversation_id] = conversation
            self.current_id = conversation.conversation_id
            self.save()
            return conversation

    def switch_conversation(self, conversation_id: str) -> bool:
        with self._lock:
            if conversation_id not in self.conversations:
                return False
            self.current_id = conversation_id
            self.save()
            return True

    def delete_conversation(self, conversation_id: str) -> bool:
        with self._lock:
            if conversation_id not in self.conversations:
                return False
            self.conversations.pop(conversation_id)
            if not self.conversations:
                self.create_conversation()
            elif self.current_id == conversation_id:
                self.current_id = next(iter(self.conversations))
            self.save()
            return True

    def rename_conversation(self, conversation_id: str, title: str) -> bool:
        with self._lock:
            conversation = self.conversations.get(conversation_id)
            if conversation is None:
                return False
            conversation.title = title.strip() or conversation.title
            conversation.updated_at = utc_now_iso()
            self.save()
            return True

    def list_conversations(self) -> list[dict[str, Any]]:
        with self._lock:
            items = []
            for conversation in sorted(self.conversations.values(), key=lambda item: item.updated_at, reverse=True):
                preview = conversation.messages[-1].content[:60] if conversation.messages else ""
                items.append(
                    {
                        "id": conversation.conversation_id,
                        "title": conversation.title,
                        "message_count": len(conversation.messages),
                        "created_at": conversation.created_at,
                        "updated_at": conversation.updated_at,
                        "is_current": conversation.conversation_id == self.current_id,
                        "last_message_preview": preview,
                    }
                )
            return items

    def add_user_message(self, content: str, save: bool = True, **metadata) -> Message:
        with self._lock:
            message = self.current_conversation.add_message("user", content, **metadata)
            if save:
                self.save()
            return message

    def add_assistant_message(self, content: str, save: bool = True, **metadata) -> Message:
        with self._lock:
            message = self.current_conversation.add_message("assistant", content, **metadata)
            if save:
                self.save()
            return message

    def get_history(self, conversation_id: str | None = None, max_turns: int | None = None) -> list[dict[str, str]]:
        with self._lock:
            conversation = self.current_conversation if conversation_id is None else self.conversations.get(conversation_id)
            if conversation is None:
                return []
            return conversation.to_llm_history(max_turns or self.max_history_turns)

    def clear_history(self, conversation_id: str | None = None) -> None:
        with self._lock:
            conversation = self.current_conversation if conversation_id is None else self.conversations.get(conversation_id)
            if conversation is None:
                return
            conversation.messages = []
            conversation.title = "新对话"
            conversation.updated_at = utc_now_iso()
            self.save()

    def load(self) -> None:
        if not self.storage_path.exists():
            old_path = self.storage_path.with_suffix(".jsonl")
            if old_path.exists():
                old_path.replace(self.storage_path)
                # 迁移完成后继续往下读取新路径
            else:
                self.storage_path.parent.mkdir(parents=True, exist_ok=True)
                self.conversations = {}
                self.current_id = None
                self.create_conversation()
                return

        try:
            data = json.loads(self.storage_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            broken_path = self.storage_path.with_suffix(f"{self.storage_path.suffix}.broken")
            self.storage_path.replace(broken_path)
            self.conversations = {}
            self.current_id = None
            self.create_conversation()
            return

        self.current_id = data.get("current_id")
        self.conversations = {
            key: Conversation.from_dict(value)
            for key, value in data.get("conversations", {}).items()
        }
        if not self.conversations:
            self.current_id = None
            self.create_conversation()
            return
        if self.current_id not in self.conversations:
            self.current_id = next(iter(self.conversations))
            self.save()

    def save(self) -> None:
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "current_id": self.current_id,
            "conversations": {
                conversation_id: {
                    "conversation_id": conversation.conversation_id,
                    "title": conversation.title,
                    "created_at": conversation.created_at,
                    "updated_at": conversation.updated_at,
                    "metadata": conversation.metadata,
                    "messages": [asdict(message) for message in conversation.messages],
                }
                for conversation_id, conversation in self.conversations.items()
            },
        }
        tmp_path = self.storage_path.with_suffix(f"{self.storage_path.suffix}.tmp")
        tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        fd = os.open(tmp_path, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
        tmp_path.replace(self.storage_path)


def auto_title_from_text(text: str, limit: int = 24) -> str:
    compact = " ".join(text.strip().split())
    if not compact:
        return "新对话"
    return compact[:limit]
