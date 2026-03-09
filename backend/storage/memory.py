"""In-memory storage implementations. Suitable for testing and development; data is lost on restart."""

from __future__ import annotations

import math
import uuid
from typing import Any

from backend.interfaces import EmbeddingStore, ChatMessage
from backend.interfaces.storage import (
    ChatId,
    ChatRecord,
    ChatStore,
    MemoryId,
    MemoryRecord,
    MemoryStore,
    UserId, ResponseInProgressId, ResponseInProgressRecord,
)
from backend.utils import now_iso


class InMemoryChatStore(ChatStore):
    """In-memory implementation of ChatStore. Suitable for testing and development; data is lost on restart."""

    def __init__(self) -> None:
        self._chats: dict[ChatId, ChatRecord] = {}
        self._messages: dict[ChatId, list[ChatMessage]] = {}

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
        chats = [c for c in self._chats.values() if c.user_id == user_id]
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
        return self._chats.get(chat_id)

    async def get_chat_messages(self, chat_id: ChatId) -> list[ChatMessage]:
        return self._messages.get(chat_id, []).copy()

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
            title=title,
            model=model,
            archived=False,
            created_at=now,
            updated_at=now,
            responses=[]
        )
        self._chats[chat_id] = record
        self._messages[chat_id] = []
        return record

    async def update_chat(
            self,
            chat_id: ChatId,
            *,
            title: str | None = None,
            model: str | None = None,
            archived: bool | None = None,
    ) -> ChatRecord | None:
        record = self._chats.get(chat_id)
        if not record:
            return None
        record.title = title if title is not None else record.title
        record.model = model if model is not None else record.model
        record.archived = archived if archived is not None else record.archived
        record.updated_at = now_iso()
        return record

    async def append_messages(self, chat_id: ChatId, messages: list[ChatMessage]) -> None:
        messages_list = self._messages.get(chat_id)
        if messages_list is not None:
            messages_list.extend(messages)
        chat_record = self._chats.get(chat_id)
        if chat_record:
            chat_record.updated_at = now_iso()

    async def get_responses_in_progress(self, chat_id: ChatId) -> list[ResponseInProgressRecord]:
        record = self._chats.get(chat_id)
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
        chat_record = self._chats.get(chat_id)
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

    async def delete_chat(self, chat_id: ChatId) -> bool:
        if chat_id not in self._chats:
            return False
        del self._chats[chat_id]
        self._messages.pop(chat_id, None)
        return True


class InMemoryMemoryStore(MemoryStore):
    """In-memory implementation of MemoryStore. Suitable for testing and development; data is lost on restart."""

    def __init__(self) -> None:
        self._memories: dict[MemoryId, MemoryRecord] = {}

    async def list_memories(
            self,
            user_id: UserId,
            *,
            limit: int = 100,
            offset: int = 0,
    ) -> list[MemoryRecord]:
        items = [m for m in self._memories.values() if m.user_id == user_id]
        items.sort(key=lambda m: m.updated_at, reverse=True)
        return items[offset: offset + limit]

    async def get_memory(self, memory_id: MemoryId) -> MemoryRecord | None:
        return self._memories.get(memory_id)

    async def get_memory_by_key(self, user_id: UserId, key: str) -> MemoryRecord | None:
        key_ = key.strip()
        for m in self._memories.values():
            if m.user_id == user_id and m.key == key_:
                return m
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
        self._memories[memory_id] = record
        return record

    async def update_memory(self, memory_id: MemoryId, content: str) -> MemoryRecord | None:
        record = self._memories.get(memory_id)
        if not record:
            return None
        record.content = content.strip()
        record.updated_at = now_iso()
        return record

    async def delete_memory(self, memory_id: MemoryId) -> bool:
        if memory_id not in self._memories:
            return False
        del self._memories[memory_id]
        return True


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity; 0 if either vector has zero norm."""
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


class InMemoryEmbeddingStore(EmbeddingStore):
    """In-memory vector store for embeddings. Suitable for testing and development; data is lost on restart."""

    def __init__(self) -> None:
        # namespace -> id -> (vector, metadata)
        self._by_namespace: dict[str, dict[str, tuple[list[float], dict[str, Any]]]] = {}

    async def upsert(
            self,
            namespace: str,
            id: str,
            vector: list[float],
            metadata: dict[str, Any] | None = None,
    ) -> None:
        if namespace not in self._by_namespace:
            self._by_namespace[namespace] = {}
        self._by_namespace[namespace][id] = (list(vector), metadata.copy() if metadata else {})

    async def search(
            self,
            namespace: str,
            query_vector: list[float],
            *,
            k: int = 10,
            filter_metadata: dict[str, Any] | None = None,
    ) -> list[tuple[str, float, dict[str, Any]]]:
        items = self._by_namespace.get(namespace, {})
        if not items:
            return []
        filter_d = filter_metadata or {}
        scored: list[tuple[str, float, dict[str, Any]]] = []
        for id, (vec, meta) in items.items():
            if all(meta.get(key) == value for key, value in filter_d.items()):
                score = _cosine_similarity(query_vector, vec)
                scored.append((id, score, meta))
        scored.sort(key=lambda x: -x[1])
        return scored[:k]

    async def delete(self, namespace: str, id: str) -> bool:
        if namespace not in self._by_namespace:
            return False
        if id not in self._by_namespace[namespace]:
            return False
        del self._by_namespace[namespace][id]
        return True

    async def delete_namespace(self, namespace: str) -> None:
        self._by_namespace.pop(namespace, None)
