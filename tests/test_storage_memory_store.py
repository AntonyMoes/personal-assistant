"""Tests for InMemoryMemoryStore."""

import pytest

from backend.storage.memory import InMemoryMemoryStore


@pytest.fixture
def store():
    return InMemoryMemoryStore()


@pytest.mark.asyncio
async def test_create_memory(store):
    m = await store.create_memory("user1", key="name", content="Alice")
    assert m.id
    assert m.user_id == "user1"
    assert m.key == "name"
    assert m.content == "Alice"
    assert m.created_at
    assert m.updated_at

@pytest.mark.asyncio
async def test_get_memory(store):
    created = await store.create_memory("user1", "k", "v")
    got = await store.get_memory(created.id)
    assert got is not None
    assert got.id == created.id
    assert got.key == "k"
    assert got.content == "v"


@pytest.mark.asyncio
async def test_get_memory_missing(store):
    assert await store.get_memory("nonexistent") is None


@pytest.mark.asyncio
async def test_list_memories(store):
    await store.create_memory("user1", "a", "1")
    await store.create_memory("user1", "b", "2")
    items = await store.list_memories("user1")
    assert len(items) == 2
    keys = {m.key for m in items}
    assert keys == {"a", "b"}


@pytest.mark.asyncio
async def test_list_memories_returns_all_for_user(store):
    """list_memories has no chat_id param; returns all memories for the user."""
    await store.create_memory("user1", "g", "global")
    await store.create_memory("user1", "c", "chat")
    items = await store.list_memories("user1")
    assert len(items) == 2
    keys = {m.key for m in items}
    assert keys == {"g", "c"}


@pytest.mark.asyncio
async def test_list_memories_filter_user(store):
    await store.create_memory("user1", "k1", "v1")
    await store.create_memory("user2", "k2", "v2")
    items = await store.list_memories("user1")
    assert len(items) == 1
    assert items[0].key == "k1"


@pytest.mark.asyncio
async def test_update_memory(store):
    created = await store.create_memory("user1", "k", "old")
    updated = await store.update_memory(created.id, "new")
    assert updated is not None
    assert updated.content == "new"
    assert (await store.get_memory(created.id)).content == "new"


@pytest.mark.asyncio
async def test_update_memory_missing(store):
    assert await store.update_memory("nonexistent", "x") is None


@pytest.mark.asyncio
async def test_delete_memory(store):
    created = await store.create_memory("user1", "k", "v")
    ok = await store.delete_memory(created.id)
    assert ok is True
    assert await store.get_memory(created.id) is None
    assert await store.delete_memory("nonexistent") is False
