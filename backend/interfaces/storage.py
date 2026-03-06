"""Storage interfaces: chats, memories, embeddings. Implementations are swappable."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

# Type aliases for IDs
ChatId = str
MemoryId = str
UserId = str


@dataclass
class ChatRecord:
    """A chat session: metadata + ordered messages (stored separately or inline)."""

    id: ChatId
    user_id: UserId
    title: str
    model: str
    archived: bool
    created_at: str  # ISO datetime
    updated_at: str
    message_ids: list[str] | None = None  # if messages stored separately


@dataclass
class MemoryRecord:
    """A single stored memory (thing the user asked the service to remember)."""

    id: MemoryId
    user_id: UserId
    key: str  # or scope/tag
    content: str
    created_at: str
    updated_at: str
    chat_id: ChatId | None = None  # None = global memory


class ChatStore(Protocol):
    """CRUD and list for chats. Message history may be part of chat or separate."""

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
        ...

    async def get_chat(self, chat_id: ChatId) -> ChatRecord | None:
        ...

    async def get_chat_messages(self, chat_id: ChatId) -> list[dict[str, Any]]:
        """Return ordered messages for the chat (role, content, etc.)."""
        ...

    async def create_chat(
        self,
        user_id: UserId,
        title: str,
        model: str,
    ) -> ChatRecord:
        ...

    async def update_chat(
        self,
        chat_id: ChatId,
        *,
        title: str | None = None,
        model: str | None = None,
        archived: bool | None = None,
    ) -> ChatRecord | None:
        ...

    async def append_messages(self, chat_id: ChatId, messages: list[dict[str, Any]]) -> None:
        ...

    async def delete_chat(self, chat_id: ChatId) -> bool:
        ...


class MemoryStore(Protocol):
    """CRUD and list for memories."""

    async def list_memories(
        self,
        user_id: UserId,
        *,
        chat_id: ChatId | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[MemoryRecord]:
        ...

    async def get_memory(self, memory_id: MemoryId) -> MemoryRecord | None:
        ...

    async def create_memory(
        self,
        user_id: UserId,
        key: str,
        content: str,
        chat_id: ChatId | None = None,
    ) -> MemoryRecord:
        ...

    async def update_memory(self, memory_id: MemoryId, content: str) -> MemoryRecord | None:
        ...

    async def delete_memory(self, memory_id: MemoryId) -> bool:
        ...


class EmbeddingStore(Protocol):
    """Vector store for embeddings: upsert, search, delete. Used by RAG/tools."""

    async def upsert(
        self,
        namespace: str,  # e.g. "chats", "memories", "obsidian"
        id: str,
        vector: list[float],
        metadata: dict[str, Any] | None = None,
    ) -> None:
        ...

    async def search(
        self,
        namespace: str,
        query_vector: list[float],
        *,
        k: int = 10,
        filter_metadata: dict[str, Any] | None = None,
    ) -> list[tuple[str, float, dict[str, Any]]]:
        """Return list of (id, score, metadata)."""
        ...

    async def delete(self, namespace: str, id: str) -> bool:
        ...

    async def delete_namespace(self, namespace: str) -> None:
        """Remove all vectors in the namespace."""
        ...
