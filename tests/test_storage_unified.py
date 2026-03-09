"""Unified storage tests: same test logic for memory and file backends so both stores behave identically."""

import pytest

from backend.interfaces import ChatMessage
from backend.interfaces.storage import PendingToolCall
from backend.storage.file import FileSystemChatStore, FileSystemMemoryStore
from backend.storage.memory import InMemoryChatStore, InMemoryMemoryStore


# --- MemoryStore: one set of tests for both backends ---


@pytest.fixture(params=["memory", "file"])
def memory_store(request, tmp_path):
    """MemoryStore: in-memory or file-based (same interface)."""
    if request.param == "memory":
        return InMemoryMemoryStore()
    return FileSystemMemoryStore(tmp_path)


@pytest.mark.asyncio
async def test_memory_create_and_get(memory_store):
    m = await memory_store.create_memory("user1", "name", "Alice")
    assert m.id
    assert m.user_id == "user1"
    assert m.key == "name"
    assert m.content == "Alice"
    got = await memory_store.get_memory(m.id)
    assert got is not None
    assert got.content == "Alice"


@pytest.mark.asyncio
async def test_memory_get_by_key(memory_store):
    await memory_store.create_memory("user1", "k", "v")
    got = await memory_store.get_memory_by_key("user1", "k")
    assert got is not None
    assert got.content == "v"
    assert await memory_store.get_memory_by_key("user1", "other") is None


@pytest.mark.asyncio
async def test_memory_list(memory_store):
    await memory_store.create_memory("user1", "a", "1")
    await memory_store.create_memory("user1", "b", "2")
    await memory_store.create_memory("user2", "c", "3")
    items = await memory_store.list_memories("user1")
    assert len(items) == 2
    keys = {m.key for m in items}
    assert keys == {"a", "b"}


@pytest.mark.asyncio
async def test_memory_list_filter_user(memory_store):
    await memory_store.create_memory("user1", "k1", "v1")
    await memory_store.create_memory("user2", "k2", "v2")
    items = await memory_store.list_memories("user1")
    assert len(items) == 1
    assert items[0].key == "k1"


@pytest.mark.asyncio
async def test_memory_update_and_delete(memory_store):
    m = await memory_store.create_memory("user1", "k", "old")
    updated = await memory_store.update_memory(m.id, "new")
    assert updated is not None
    assert updated.content == "new"
    ok = await memory_store.delete_memory(m.id)
    assert ok is True
    assert await memory_store.get_memory(m.id) is None
    assert await memory_store.delete_memory("nonexistent") is False


@pytest.mark.asyncio
async def test_memory_get_missing(memory_store):
    assert await memory_store.get_memory("nonexistent") is None


@pytest.mark.asyncio
async def test_memory_update_missing(memory_store):
    assert await memory_store.update_memory("nonexistent", "x") is None


# --- ChatStore: one set of tests for both backends ---


@pytest.fixture(params=["memory", "file"])
def chat_store(request, tmp_path):
    """ChatStore: in-memory or file-based (same interface)."""
    if request.param == "memory":
        return InMemoryChatStore()
    return FileSystemChatStore(tmp_path)


@pytest.mark.asyncio
async def test_chat_create_and_get(chat_store):
    chat = await chat_store.create_chat("user1", "My Chat", "stub")
    assert chat.id
    assert chat.user_id == "user1"
    assert chat.title == "My Chat"
    assert chat.model == "stub"
    assert chat.archived is False
    got = await chat_store.get_chat(chat.id)
    assert got is not None
    assert got.id == chat.id
    assert got.title == "My Chat"


@pytest.mark.asyncio
async def test_chat_get_missing(chat_store):
    assert await chat_store.get_chat("nonexistent") is None


@pytest.mark.asyncio
async def test_chat_list(chat_store):
    await chat_store.create_chat("user1", "First", "stub")
    await chat_store.create_chat("user1", "Second", "stub")
    await chat_store.create_chat("user2", "Other", "stub")
    chats = await chat_store.list_chats("user1")
    assert len(chats) == 2
    titles = {c.title for c in chats}
    assert titles == {"First", "Second"}


@pytest.mark.asyncio
async def test_chat_list_filter_user(chat_store):
    await chat_store.create_chat("user1", "U1", "stub")
    await chat_store.create_chat("user2", "U2", "stub")
    chats = await chat_store.list_chats("user1")
    assert len(chats) == 1
    assert chats[0].title == "U1"


@pytest.mark.asyncio
async def test_chat_messages(chat_store):
    chat = await chat_store.create_chat("user1", "Chat", "stub")
    msgs = await chat_store.get_chat_messages(chat.id)
    assert msgs == []
    await chat_store.append_messages(chat.id, [ChatMessage("user", "hi")])
    await chat_store.append_messages(chat.id, [ChatMessage("assistant", "hello")])
    msgs = await chat_store.get_chat_messages(chat.id)
    assert len(msgs) == 2
    assert msgs[0].role == "user" and msgs[0].content == "hi"
    assert msgs[1].role == "assistant" and msgs[1].content == "hello"


@pytest.mark.asyncio
async def test_chat_update(chat_store):
    chat = await chat_store.create_chat("user1", "Old", "stub")
    updated = await chat_store.update_chat(chat.id, title="New")
    assert updated is not None
    assert updated.title == "New"
    got = await chat_store.get_chat(chat.id)
    assert got.title == "New"


@pytest.mark.asyncio
async def test_chat_update_missing(chat_store):
    assert await chat_store.update_chat("nonexistent", title="X") is None


@pytest.mark.asyncio
async def test_chat_delete(chat_store):
    chat = await chat_store.create_chat("user1", "To Delete", "stub")
    await chat_store.append_messages(chat.id, [ChatMessage("user", "x")])
    ok = await chat_store.delete_chat(chat.id)
    assert ok is True
    assert await chat_store.get_chat(chat.id) is None
    assert await chat_store.get_chat_messages(chat.id) == []
    assert await chat_store.delete_chat("nonexistent") is False


# --- ChatStore: response-in-progress (pending tool calls) ---


@pytest.mark.asyncio
async def test_chat_create_response_in_progress(chat_store):
    chat = await chat_store.create_chat("user1", "Chat", "stub")
    resp = await chat_store.create_response_in_progress(chat.id)
    assert resp.id
    assert resp.pending_content == ""
    assert resp.internal_messages_context == []
    assert resp.pending_tool_calls == []

    in_progress = await chat_store.get_responses_in_progress(chat.id)
    assert len(in_progress) == 1
    assert in_progress[0].id == resp.id


@pytest.mark.asyncio
async def test_chat_set_response_in_progress_with_pending_tool_calls(chat_store):
    chat = await chat_store.create_chat("user1", "Chat", "stub")
    resp = await chat_store.create_response_in_progress(chat.id)
    pending = PendingToolCall(
        id="tc-1",
        tool_name="read_file",
        args={"path": "/tmp/x"},
        permission=None,
    )
    resp.pending_tool_calls.append(pending)
    resp.pending_content = "Waiting for approval..."
    await chat_store.set_response_in_progress(chat.id, resp.id, resp)

    in_progress = await chat_store.get_responses_in_progress(chat.id)
    assert len(in_progress) == 1
    assert len(in_progress[0].pending_tool_calls) == 1
    assert in_progress[0].pending_tool_calls[0].id == "tc-1"
    assert in_progress[0].pending_tool_calls[0].tool_name == "read_file"
    assert in_progress[0].pending_tool_calls[0].args == {"path": "/tmp/x"}
    assert in_progress[0].pending_content == "Waiting for approval..."


@pytest.mark.asyncio
async def test_chat_clear_response_in_progress(chat_store):
    chat = await chat_store.create_chat("user1", "Chat", "stub")
    resp = await chat_store.create_response_in_progress(chat.id)
    resp.pending_tool_calls.append(
        PendingToolCall("tc-1", "tool", {}, None)
    )
    await chat_store.set_response_in_progress(chat.id, resp.id, resp)
    assert len((await chat_store.get_responses_in_progress(chat.id))[0].pending_tool_calls) == 1

    await chat_store.set_response_in_progress(chat.id, resp.id, None)
    in_progress = await chat_store.get_responses_in_progress(chat.id)
    assert len(in_progress) == 0


@pytest.mark.asyncio
async def test_chat_response_in_progress_internal_messages(chat_store):
    chat = await chat_store.create_chat("user1", "Chat", "stub")
    resp = await chat_store.create_response_in_progress(chat.id)
    resp.internal_messages_context = [
        ChatMessage("assistant", "Let me check.", tool_calls=[{"id": "tc-1", "name": "read", "arguments": {}}]),
        ChatMessage("tool", "file contents"),
    ]
    await chat_store.set_response_in_progress(chat.id, resp.id, resp)

    in_progress = await chat_store.get_responses_in_progress(chat.id)
    assert len(in_progress) == 1
    assert len(in_progress[0].internal_messages_context) == 2
    assert in_progress[0].internal_messages_context[0].role == "assistant"
    assert in_progress[0].internal_messages_context[1].role == "tool"


@pytest.mark.asyncio
async def test_chat_get_responses_in_progress_empty(chat_store):
    chat = await chat_store.create_chat("user1", "Chat", "stub")
    in_progress = await chat_store.get_responses_in_progress(chat.id)
    assert in_progress == []


@pytest.mark.asyncio
async def test_chat_get_responses_in_progress_nonexistent_chat(chat_store):
    in_progress = await chat_store.get_responses_in_progress("nonexistent")
    assert in_progress == []
