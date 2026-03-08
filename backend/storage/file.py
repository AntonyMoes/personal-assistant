"""File-based storage implementations. Data persists to disk under configurable paths."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from backend.interfaces.storage import (
    ChatId,
    ChatRecord,
    ChatStore,
    MemoryId,
    MemoryRecord,
    MemoryStore,
    UserId,
)
from backend.utils import now_iso


# --- FileSystemChatStore ---


def _chat_to_dict(c: ChatRecord) -> dict:
    return {
        "id": c.id,
        "user_id": c.user_id,
        "title": c.title,
        "model": c.model,
        "archived": c.archived,
        "created_at": c.created_at,
        "updated_at": c.updated_at,
    }


def _dict_to_chat(d: dict) -> ChatRecord:
    return ChatRecord(
        id=d["id"],
        user_id=d["user_id"],
        title=d["title"],
        model=d["model"],
        archived=bool(d.get("archived", False)),
        created_at=d["created_at"],
        updated_at=d["updated_at"],
        message_ids=None,
    )


class FileSystemChatStore(ChatStore):
    """ChatStore that persists to disk: index of chats + one file per chat for messages."""

    def __init__(self, root_path: str | Path) -> None:
        self._root = Path(root_path).resolve()
        self._root.mkdir(parents=True, exist_ok=True)
        self._index_path = self._root / "index.json"
        if not self._index_path.exists():
            self._index_path.write_text('{"chats":[]}', encoding="utf-8")

    def _read_index(self) -> dict:
        raw = self._index_path.read_text(encoding="utf-8")
        return json.loads(raw) if raw.strip() else {"chats": []}

    def _write_index(self, data: dict) -> None:
        self._index_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _messages_path(self, chat_id: ChatId) -> Path:
        return self._root / f"{chat_id}.json"

    def _read_messages(self, chat_id: ChatId) -> list[dict[str, Any]]:
        path = self._messages_path(chat_id)
        if not path.exists():
            return []
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw) if raw.strip() else {}
        return data.get("messages", [])

    def _write_messages(self, chat_id: ChatId, messages: list[dict[str, Any]]) -> None:
        self._messages_path(chat_id).write_text(
            json.dumps({"messages": messages}, indent=2), encoding="utf-8"
        )

    async def list_chats(
        self,
        user_id: UserId,
        *,
        archived: bool | None = None,
        sort: str = "updated_at",
        order: str = "desc",
        limit: int = 100,
        offset: int = 0,
    ) -> list[ChatRecord]:
        index = self._read_index()
        chats = [_dict_to_chat(d) for d in index.get("chats", []) if d.get("user_id") == user_id]
        if archived is not None:
            chats = [c for c in chats if c.archived == archived]
        reverse = order.lower() == "desc"
        if sort == "updated_at":
            chats.sort(key=lambda c: c.updated_at, reverse=reverse)
        elif sort == "created_at":
            chats.sort(key=lambda c: c.created_at, reverse=reverse)
        elif sort == "title":
            chats.sort(key=lambda c: c.title.lower(), reverse=reverse)
        return chats[offset : offset + limit]

    async def get_chat(self, chat_id: ChatId) -> ChatRecord | None:
        index = self._read_index()
        for d in index.get("chats", []):
            if d.get("id") == chat_id:
                return _dict_to_chat(d)
        return None

    async def get_chat_messages(self, chat_id: ChatId) -> list[dict[str, Any]]:
        return self._read_messages(chat_id).copy()

    async def create_chat(
        self,
        user_id: UserId,
        title: str,
        model: str,
    ) -> ChatRecord:
        chat_id = uuid.uuid4().hex
        now = now_iso()
        record = ChatRecord(
            id=chat_id,
            user_id=user_id,
            title=title or "New chat",
            model=model or "stub",
            archived=False,
            created_at=now,
            updated_at=now,
            message_ids=[],
        )
        index = self._read_index()
        index.setdefault("chats", []).append(_chat_to_dict(record))
        self._write_index(index)
        self._write_messages(chat_id, [])
        return record

    async def update_chat(
        self,
        chat_id: ChatId,
        *,
        title: str | None = None,
        model: str | None = None,
        archived: bool | None = None,
    ) -> ChatRecord | None:
        record = await self.get_chat(chat_id)
        if not record:
            return None
        new_title = title if title is not None else record.title
        new_model = model if model is not None else record.model
        new_archived = archived if archived is not None else record.archived
        updated = ChatRecord(
            id=record.id,
            user_id=record.user_id,
            title=new_title,
            model=new_model,
            archived=new_archived,
            created_at=record.created_at,
            updated_at=now_iso(),
            message_ids=record.message_ids,
        )
        index = self._read_index()
        for i, d in enumerate(index.get("chats", [])):
            if d.get("id") == chat_id:
                index["chats"][i] = _chat_to_dict(updated)
                break
        self._write_index(index)
        return updated

    async def append_messages(self, chat_id: ChatId, messages: list[dict[str, Any]]) -> None:
        if not messages:
            return
        record = await self.get_chat(chat_id)
        if not record:
            return
        current = self._read_messages(chat_id)
        current.extend(messages)
        self._write_messages(chat_id, current)
        index = self._read_index()
        for i, d in enumerate(index.get("chats", [])):
            if d.get("id") == chat_id:
                index["chats"][i]["updated_at"] = now_iso()
                break
        self._write_index(index)

    async def delete_chat(self, chat_id: ChatId) -> bool:
        index = self._read_index()
        before = len(index.get("chats", []))
        index["chats"] = [d for d in index.get("chats", []) if d.get("id") != chat_id]
        if len(index["chats"]) == before:
            return False
        self._write_index(index)
        path = self._messages_path(chat_id)
        if path.exists():
            path.unlink()
        return True


# --- FileSystemMemoryStore ---


def _memory_to_dict(m: MemoryRecord) -> dict:
    return {
        "id": m.id,
        "user_id": m.user_id,
        "key": m.key,
        "content": m.content,
        "created_at": m.created_at,
        "updated_at": m.updated_at,
    }


def _dict_to_memory(d: dict) -> MemoryRecord:
    return MemoryRecord(
        id=d["id"],
        user_id=d["user_id"],
        key=d["key"],
        content=d["content"],
        created_at=d["created_at"],
        updated_at=d["updated_at"],
    )


class FileSystemMemoryStore(MemoryStore):
    """MemoryStore that persists to a single index.json file."""

    def __init__(self, root_path: str | Path) -> None:
        self._root = Path(root_path).resolve()
        self._root.mkdir(parents=True, exist_ok=True)
        self._index_path = self._root / "index.json"
        if not self._index_path.exists():
            self._index_path.write_text('{"memories":[]}', encoding="utf-8")

    def _read_index(self) -> dict:
        raw = self._index_path.read_text(encoding="utf-8")
        return json.loads(raw) if raw.strip() else {"memories": []}

    def _write_index(self, data: dict) -> None:
        self._index_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    async def list_memories(
        self,
        user_id: UserId,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[MemoryRecord]:
        index = self._read_index()
        items = [_dict_to_memory(d) for d in index.get("memories", []) if d.get("user_id") == user_id]
        items.sort(key=lambda m: m.updated_at, reverse=True)
        return items[offset : offset + limit]

    async def get_memory(self, memory_id: MemoryId) -> MemoryRecord | None:
        index = self._read_index()
        for d in index.get("memories", []):
            if d.get("id") == memory_id:
                return _dict_to_memory(d)
        return None

    async def get_memory_by_key(self, user_id: UserId, key: str) -> MemoryRecord | None:
        key_ = key.strip()
        index = self._read_index()
        for d in index.get("memories", []):
            if d.get("user_id") == user_id and d.get("key") == key_:
                return _dict_to_memory(d)
        return None

    async def create_memory(
        self,
        user_id: UserId,
        key: str,
        content: str,
    ) -> MemoryRecord:
        memory_id = uuid.uuid4().hex
        now = now_iso()
        record = MemoryRecord(
            id=memory_id,
            user_id=user_id,
            key=key.strip(),
            content=content.strip(),
            created_at=now,
            updated_at=now,
        )
        index = self._read_index()
        index.setdefault("memories", []).append(_memory_to_dict(record))
        self._write_index(index)
        return record

    async def update_memory(self, memory_id: MemoryId, content: str) -> MemoryRecord | None:
        index = self._read_index()
        for i, d in enumerate(index.get("memories", [])):
            if d.get("id") == memory_id:
                index["memories"][i]["content"] = content.strip()
                index["memories"][i]["updated_at"] = now_iso()
                self._write_index(index)
                return _dict_to_memory(index["memories"][i])
        return None

    async def delete_memory(self, memory_id: MemoryId) -> bool:
        index = self._read_index()
        before = len(index.get("memories", []))
        index["memories"] = [d for d in index.get("memories", []) if d.get("id") != memory_id]
        if len(index["memories"]) == before:
            return False
        self._write_index(index)
        return True
