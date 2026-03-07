"""In-memory storage implementations. Suitable for testing and development; data is lost on restart."""

from __future__ import annotations

import math
import uuid
from datetime import datetime, timezone
from typing import Any

from backend.interfaces import EmbeddingStore
from backend.interfaces.storage import (
    ChatId,
    ChatRecord,
    ChatStore,
    MemoryId,
    MemoryRecord,
    MemoryStore,
    UserId,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


class InMemoryChatStore(ChatStore):
    """In-memory implementation of ChatStore. Suitable for testing and development; data is lost on restart."""

    def __init__(self) -> None:
        self._chats: dict[ChatId, ChatRecord] = {}
        self._messages: dict[ChatId, list[dict[str, Any]]] = {}

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
        return chats[offset : offset + limit]

    async def get_chat(self, chat_id: ChatId) -> ChatRecord | None:
        return self._chats.get(chat_id)

    async def get_chat_messages(self, chat_id: ChatId) -> list[dict[str, Any]]:
        return self._messages.get(chat_id, []).copy()

    async def create_chat(
        self,
        user_id: UserId,
        title: str,
        model: str,
    ) -> ChatRecord:
        chat_id = uuid.uuid4().hex
        now = _now_iso()
        record = ChatRecord(
            id=chat_id,
            user_id=user_id,
            title=title,
            model=model,
            archived=False,
            created_at=now,
            updated_at=now,
            message_ids=[],
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
            updated_at=_now_iso(),
            message_ids=record.message_ids,
        )
        self._chats[chat_id] = updated
        return updated

    async def append_messages(self, chat_id: ChatId, messages: list[dict[str, Any]]) -> None:
        if chat_id in self._messages:
            self._messages[chat_id].extend(messages)
        record = self._chats.get(chat_id)
        if record:
            self._chats[chat_id] = ChatRecord(
                id=record.id,
                user_id=record.user_id,
                title=record.title,
                model=record.model,
                archived=record.archived,
                created_at=record.created_at,
                updated_at=_now_iso(),
                message_ids=record.message_ids,
            )

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
        return items[offset : offset + limit]

    async def get_memory(self, memory_id: MemoryId) -> MemoryRecord | None:
        return self._memories.get(memory_id)

    async def create_memory(
        self,
        user_id: UserId,
        key: str,
        content: str,
    ) -> MemoryRecord:
        memory_id = uuid.uuid4().hex
        now = _now_iso()
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
        updated = MemoryRecord(
            id=record.id,
            user_id=record.user_id,
            key=record.key,
            content=content.strip(),
            created_at=record.created_at,
            updated_at=_now_iso(),
        )
        self._memories[memory_id] = updated
        return updated

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
