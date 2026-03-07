"""Tests for RememberTool."""

import pytest

from backend.interfaces.tools import Capability, ToolContext
from backend.storage.memory import InMemoryMemoryStore
from backend.tools.remember import RememberTool


@pytest.fixture
def tool():
    return RememberTool()


@pytest.fixture
def memory_store():
    return InMemoryMemoryStore()


def test_remember_tool_name_and_capabilities(tool):
    assert tool.name == "remember"
    assert Capability.MEMORY_WRITE in tool.capabilities()


def test_remember_tool_args_schema(tool):
    schema = tool.args_schema()
    assert schema["type"] == "object"
    assert "key" in schema["properties"]
    assert "content" in schema["properties"]
    assert "key" in schema["required"] and "content" in schema["required"]


@pytest.mark.asyncio
async def test_remember_tool_preview(tool):
    ctx = ToolContext(user_id="u1", chat_id="c1", memory_store=None)
    preview = await tool.preview({"key": "name", "content": "Alice"}, ctx)
    assert preview.tool_name == "remember"
    assert "name" in preview.summary
    assert "Alice" in preview.summary


@pytest.mark.asyncio
async def test_remember_tool_call_without_memory_store(tool):
    ctx = ToolContext(user_id="u1", chat_id="c1", memory_store=None)
    result = await tool.call({"key": "k", "content": "v"}, ctx)
    assert result.success is False
    assert "not available" in result.content


@pytest.mark.asyncio
async def test_remember_tool_call_creates_memory(tool, memory_store):
    ctx = ToolContext(user_id="u1", chat_id="c1", memory_store=memory_store)
    result = await tool.call({"key": "name", "content": "Alice"}, ctx)
    assert result.success is True
    assert "Saved" in result.content
    memories = await memory_store.list_memories("u1")
    assert len(memories) == 1
    assert memories[0].key == "name"
    assert memories[0].content == "Alice"
    assert memories[0].user_id == "u1"


@pytest.mark.asyncio
async def test_remember_tool_call_global_scope(tool, memory_store):
    ctx = ToolContext(user_id="u1", chat_id=None, memory_store=memory_store)
    result = await tool.call({"key": "pref", "content": "dark mode"}, ctx)
    assert result.success is True
    memories = await memory_store.list_memories("u1")
    assert len(memories) == 1


@pytest.mark.asyncio
async def test_remember_tool_call_missing_key_or_content(tool, memory_store):
    ctx = ToolContext(user_id="u1", chat_id="c1", memory_store=memory_store)
    r1 = await tool.call({"key": "", "content": "v"}, ctx)
    assert r1.success is False
    r2 = await tool.call({"key": "k", "content": ""}, ctx)
    assert r2.success is False
