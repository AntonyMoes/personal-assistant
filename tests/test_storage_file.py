"""Tests for file-based ChatStore and MemoryStore. Use tmp_path so real file store data is not touched."""

import pytest

from backend.storage.file import FileSystemChatStore, FileSystemMemoryStore


# --- FileSystemChatStore ---


@pytest.fixture
def chat_store(tmp_path):
    return FileSystemChatStore(tmp_path)


@pytest.mark.asyncio
async def test_fs_chat_create_and_get(chat_store):
    chat = await chat_store.create_chat("user1", "My Chat", "stub")
    assert chat.id
    assert chat.user_id == "user1"
    assert chat.title == "My Chat"
    assert chat.model == "stub"
    assert not chat.archived
    got = await chat_store.get_chat(chat.id)
    assert got is not None
    assert got.id == chat.id
    assert got.title == "My Chat"


@pytest.mark.asyncio
async def test_fs_chat_list(chat_store):
    await chat_store.create_chat("user1", "First", "stub")
    await chat_store.create_chat("user1", "Second", "stub")
    await chat_store.create_chat("user2", "Other", "stub")
    chats = await chat_store.list_chats("user1")
    assert len(chats) == 2
    titles = {c.title for c in chats}
    assert titles == {"First", "Second"}


@pytest.mark.asyncio
async def test_fs_chat_messages(chat_store):
    chat = await chat_store.create_chat("user1", "Chat", "stub")
    msgs = await chat_store.get_chat_messages(chat.id)
    assert msgs == []
    await chat_store.append_messages(chat.id, [{"role": "user", "content": "hi"}])
    await chat_store.append_messages(chat.id, [{"role": "assistant", "content": "hello"}])
    msgs = await chat_store.get_chat_messages(chat.id)
    assert len(msgs) == 2
    assert msgs[0]["role"] == "user" and msgs[0]["content"] == "hi"
    assert msgs[1]["role"] == "assistant" and msgs[1]["content"] == "hello"


@pytest.mark.asyncio
async def test_fs_chat_update(chat_store):
    chat = await chat_store.create_chat("user1", "Old", "stub")
    updated = await chat_store.update_chat(chat.id, title="New")
    assert updated is not None
    assert updated.title == "New"
    got = await chat_store.get_chat(chat.id)
    assert got.title == "New"


@pytest.mark.asyncio
async def test_fs_chat_delete(chat_store):
    chat = await chat_store.create_chat("user1", "To Delete", "stub")
    await chat_store.append_messages(chat.id, [{"role": "user", "content": "x"}])
    ok = await chat_store.delete_chat(chat.id)
    assert ok is True
    assert await chat_store.get_chat(chat.id) is None
    assert await chat_store.get_chat_messages(chat.id) == []
    assert await chat_store.delete_chat("nonexistent") is False


@pytest.mark.asyncio
async def test_fs_chat_persistence(chat_store, tmp_path):
    chat = await chat_store.create_chat("user1", "Persist", "stub")
    await chat_store.append_messages(chat.id, [{"role": "user", "content": "saved"}])
    store2 = FileSystemChatStore(tmp_path)
    got = await store2.get_chat(chat.id)
    assert got is not None
    assert got.title == "Persist"
    msgs = await store2.get_chat_messages(chat.id)
    assert len(msgs) == 1 and msgs[0]["content"] == "saved"


# --- FileSystemMemoryStore ---


@pytest.fixture
def memory_store(tmp_path):
    return FileSystemMemoryStore(tmp_path)


@pytest.mark.asyncio
async def test_fs_memory_create_and_get(memory_store):
    m = await memory_store.create_memory("user1", "name", "Alice")
    assert m.id
    assert m.user_id == "user1"
    assert m.key == "name"
    assert m.content == "Alice"
    got = await memory_store.get_memory(m.id)
    assert got is not None
    assert got.content == "Alice"


@pytest.mark.asyncio
async def test_fs_memory_get_by_key(memory_store):
    await memory_store.create_memory("user1", "k", "v")
    got = await memory_store.get_memory_by_key("user1", "k")
    assert got is not None
    assert got.content == "v"
    assert await memory_store.get_memory_by_key("user1", "other") is None


@pytest.mark.asyncio
async def test_fs_memory_list(memory_store):
    await memory_store.create_memory("user1", "a", "1")
    await memory_store.create_memory("user1", "b", "2")
    await memory_store.create_memory("user2", "c", "3")
    items = await memory_store.list_memories("user1")
    assert len(items) == 2
    keys = {m.key for m in items}
    assert keys == {"a", "b"}


@pytest.mark.asyncio
async def test_fs_memory_update_and_delete(memory_store):
    m = await memory_store.create_memory("user1", "k", "old")
    updated = await memory_store.update_memory(m.id, "new")
    assert updated is not None
    assert updated.content == "new"
    ok = await memory_store.delete_memory(m.id)
    assert ok is True
    assert await memory_store.get_memory(m.id) is None
    assert await memory_store.delete_memory("nonexistent") is False


@pytest.mark.asyncio
async def test_fs_memory_persistence(memory_store, tmp_path):
    m = await memory_store.create_memory("user1", "key", "value")
    store2 = FileSystemMemoryStore(tmp_path)
    got = await store2.get_memory(m.id)
    assert got is not None
    assert got.key == "key" and got.content == "value"
