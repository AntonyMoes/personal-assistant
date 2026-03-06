"""Tests for InMemoryChatStore."""

import pytest

from backend.storage.memory import InMemoryChatStore


@pytest.fixture
def store():
    return InMemoryChatStore()


@pytest.mark.asyncio
async def test_create_chat(store):
    chat = await store.create_chat("user1", title="Test", model="gpt-4o")
    assert chat.id
    assert chat.user_id == "user1"
    assert chat.title == "Test"
    assert chat.model == "gpt-4o"
    assert chat.archived is False
    assert chat.created_at
    assert chat.updated_at


@pytest.mark.asyncio
async def test_get_chat(store):
    created = await store.create_chat("user1", "My Chat", "gpt-4o")
    got = await store.get_chat(created.id)
    assert got is not None
    assert got.id == created.id
    assert got.title == "My Chat"


@pytest.mark.asyncio
async def test_get_chat_missing(store):
    assert await store.get_chat("nonexistent") is None


@pytest.mark.asyncio
async def test_list_chats(store):
    await store.create_chat("user1", "A", "gpt-4o")
    await store.create_chat("user1", "B", "gpt-4o")
    chats = await store.list_chats("user1")
    assert len(chats) == 2
    titles = {c.title for c in chats}
    assert titles == {"A", "B"}


@pytest.mark.asyncio
async def test_list_chats_filter_user(store):
    await store.create_chat("user1", "U1", "gpt-4o")
    await store.create_chat("user2", "U2", "gpt-4o")
    chats = await store.list_chats("user1")
    assert len(chats) == 1
    assert chats[0].title == "U1"


@pytest.mark.asyncio
async def test_update_chat_title(store):
    created = await store.create_chat("user1", "Original", "gpt-4o")
    updated = await store.update_chat(created.id, title="Renamed")
    assert updated is not None
    assert updated.title == "Renamed"
    assert (await store.get_chat(created.id)).title == "Renamed"


@pytest.mark.asyncio
async def test_update_chat_missing(store):
    assert await store.update_chat("nonexistent", title="X") is None


@pytest.mark.asyncio
async def test_append_messages(store):
    created = await store.create_chat("user1", "Chat", "gpt-4o")
    await store.append_messages(created.id, [{"role": "user", "content": "hi"}])
    msgs = await store.get_chat_messages(created.id)
    assert len(msgs) == 1
    assert msgs[0]["content"] == "hi"


@pytest.mark.asyncio
async def test_delete_chat(store):
    created = await store.create_chat("user1", "To delete", "gpt-4o")
    ok = await store.delete_chat(created.id)
    assert ok is True
    assert await store.get_chat(created.id) is None
    assert await store.delete_chat("nonexistent") is False
