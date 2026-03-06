"""In-memory ChatStore implementation. Suitable for testing and development; data is lost on restart."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from backend.interfaces.storage import ChatId, ChatRecord, ChatStore, UserId


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


class InMemoryChatStore:
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
