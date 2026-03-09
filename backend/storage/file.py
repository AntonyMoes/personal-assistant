"""File-based storage implementations. Data persists to disk under configurable paths."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from backend.interfaces import ChatMessage
from backend.interfaces.storage import (
    ChatId,
    ChatRecord,
    ChatStore,
    MemoryId,
    MemoryRecord,
    MemoryStore,
    UserId, ResponseInProgressRecord, ResponseInProgressId, PendingToolCall,
)
from backend.serialization import chat_message_from_dict, chat_message_to_dict
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
        "responses": [_response_to_dict(r) for r in c.responses],
    }


def _response_to_dict(r: ResponseInProgressRecord) -> dict:
    return {
        "id": r.id,
        "pending_content": r.pending_content,
        "internal_messages_context": [chat_message_to_dict(m) for m in r.internal_messages_context],
        "pending_tool_calls": [_tool_call_to_dict(tc) for tc in r.pending_tool_calls],
    }

def _tool_call_to_dict(tc: PendingToolCall) -> dict:
    return {
        "id": tc.id,
        "tool_name": tc.tool_name,
        "args": tc.args,
        "permission": tc.permission,
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
        responses=[_dict_to_response(rd) for rd in d["responses"]]
    )


def _dict_to_response(d: dict) -> ResponseInProgressRecord:
    return ResponseInProgressRecord(
        id=d["id"],
        pending_content=d["pending_content"],
        internal_messages_context=[chat_message_from_dict(md) for md in d["internal_messages_context"]],
        pending_tool_calls=[_dict_to_tool_call(tcd) for tcd in d["pending_tool_calls"]],
    )

def _dict_to_tool_call(d: dict) -> PendingToolCall:
    return PendingToolCall(
        id=d["id"],
        tool_name=d["tool_name"],
        args=d["args"],
        permission=d["permission"],
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

    def _read_messages(self, chat_id: ChatId) -> list[ChatMessage]:
        path = self._messages_path(chat_id)
        if not path.exists():
            return []
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw) if raw.strip() else {}
        return [chat_message_from_dict(d) for d in data.get("messages", [])]

    def _write_messages(self, chat_id: ChatId, messages: list[ChatMessage]) -> None:
        self._messages_path(chat_id).write_text(
            json.dumps({"messages": [chat_message_to_dict(m) for m in messages]}, indent=2), encoding="utf-8"
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
        return chats[offset: offset + limit]

    async def get_chat(self, chat_id: ChatId) -> ChatRecord | None:
        index = self._read_index()
        for d in index.get("chats", []):
            if d.get("id") == chat_id:
                return _dict_to_chat(d)
        return None

    def _set_chat(self, chat_id: ChatId, value: ChatRecord | None) -> bool:
        index = self._read_index()
        chats: list[dict] = index.setdefault("chats", [])
        for i, d in enumerate(chats):
            if d.get("id") == chat_id:
                if value:
                    chats[i] = _chat_to_dict(value)
                else:
                    chats.pop(i)
                self._write_index(index)
                return True

        if value:
            chats.append(_chat_to_dict(value))
            self._write_index(index)
            return True

        return False

    async def get_chat_messages(self, chat_id: ChatId) -> list[ChatMessage]:
        return self._read_messages(chat_id)

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
            responses=[],
        )
        self._set_chat(chat_id, record)
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
        record.title = title if title is not None else record.title
        record.model = model if model is not None else record.model
        record.archived = archived if archived is not None else record.archived
        record.updated_at = now_iso()
        self._set_chat(record.id, record)
        return record

    async def append_messages(self, chat_id: ChatId, messages: list[ChatMessage]) -> None:
        if not messages:
            return
        record = await self.get_chat(chat_id)
        if not record:
            return
        current = self._read_messages(chat_id)
        current.extend(messages)
        self._write_messages(chat_id, current)
        await self.update_chat(chat_id)

    async def get_responses_in_progress(self, chat_id: ChatId) -> list[ResponseInProgressRecord]:
        record = await self.get_chat(chat_id)
        return record.responses if record else []

    async def create_response_in_progress(self, chat_id: ChatId) -> ResponseInProgressRecord:
        response_id = uuid.uuid4().hex
        record = ResponseInProgressRecord(
            id=response_id,
            pending_content="",
            internal_messages_context=[],
            pending_tool_calls=[]
        )
        await self.set_response_in_progress(chat_id, response_id, record)
        return record

    async def set_response_in_progress(self, chat_id: ChatId, response_id: ResponseInProgressId,
                                       value: ResponseInProgressRecord | None) -> None:
        chat_record = await self.get_chat(chat_id)
        if not chat_record:
            return

        response_record_idx: int | None = next(
            (idx for (idx, record) in enumerate(chat_record.responses) if record.id == response_id), None)
        if value is None:
            if response_record_idx is not None:
                chat_record.responses.pop(response_record_idx)
        else:
            if response_record_idx is not None:
                chat_record.responses[response_record_idx] = value
            else:
                chat_record.responses.append(value)

        self._set_chat(chat_record.id, chat_record)

    async def delete_chat(self, chat_id: ChatId) -> bool:
        ok = self._set_chat(chat_id, None)
        if not ok:
            return False

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
        return items[offset: offset + limit]

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
