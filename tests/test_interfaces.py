"""Tests for interface dataclasses and type contracts (minimal)."""

import pytest

from backend.interfaces.storage import ChatRecord, MemoryRecord
from backend.interfaces.model import ChatMessage, ChatRequest, ModelEvent, ModelEventType
from backend.interfaces.tools import ToolPreview, ToolResult, ToolContext, Capability


def test_chat_record():
    r = ChatRecord(
        id="c1",
        user_id="u1",
        title="Chat",
        model="gpt-4o",
        archived=False,
        created_at="2024-01-01T00:00:00Z",
        updated_at="2024-01-01T00:00:00Z",
        responses=[]
    )
    assert r.title == "Chat"
    assert r.model == "gpt-4o"


def test_memory_record():
    r = MemoryRecord(
        id="m1",
        user_id="u1",
        key="pref",
        content="likes dark mode",
        created_at="2024-01-01T00:00:00Z",
        updated_at="2024-01-01T00:00:00Z",
    )
    assert r.key == "pref"


def test_chat_message():
    m = ChatMessage(role="user", content="hello")
    assert m.role == "user"
    assert m.content == "hello"


def test_chat_request():
    req = ChatRequest(messages=[ChatMessage(role="user", content="hi")], model="gpt-4o")
    assert req.model == "gpt-4o"
    assert len(req.messages) == 1


def test_model_event():
    e = ModelEvent(type=ModelEventType.TOKEN, payload={"text": "x"})
    assert e.type == ModelEventType.TOKEN
    assert e.payload["text"] == "x"


def test_tool_preview():
    p = ToolPreview(
        tool_name="write",
        title="Write file",
        summary="Create foo.txt",
        affected_resources=["foo.txt"],
        arguments={"path": "foo.txt"},
        dry_run_result=None,
    )
    assert p.tool_name == "write"
    assert p.affected_resources == ["foo.txt"]


def test_tool_result():
    r = ToolResult(success=True, content="done", data=None)
    assert r.success is True
    assert r.content == "done"


def test_tool_context():
    ctx = ToolContext(user_id="u1", chat_id="c1")
    assert ctx.user_id == "u1"
    assert ctx.chat_id == "c1"


def test_capability_enum():
    assert Capability.FILESYSTEM_WRITE.value == "filesystem_write"
    assert Capability.MEMORY_WRITE.value == "memory_write"
