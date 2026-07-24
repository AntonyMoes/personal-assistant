"""Tests for backend.context context-window trimming."""

from backend.config import ContextConfig
from backend.context import apply_context_window, estimate_message_chars
from backend.interfaces.model import ChatMessage


def _msgs(*pairs: tuple[str, str]) -> list[ChatMessage]:
    return [ChatMessage(role=r, content=c) for r, c in pairs]


def test_unlimited_when_budgets_zero():
    messages = _msgs(("user", "a"), ("assistant", "b"), ("user", "c"))
    result = apply_context_window(messages, ContextConfig(max_messages=0, max_chars=0))
    assert result.dropped_count == 0
    assert result.summarized is False
    assert result.messages == messages


def test_trim_by_max_messages_with_summary():
    messages = _msgs(
        ("user", "old1"),
        ("assistant", "old2"),
        ("user", "new1"),
        ("assistant", "new2"),
        ("user", "latest"),
    )
    result = apply_context_window(
        messages,
        ContextConfig(max_messages=2, summarize_overflow=True),
    )
    assert result.dropped_count == 3
    assert result.summarized is True
    assert result.messages[0].role == "system"
    assert "Earlier conversation" in result.messages[0].content
    assert "old1" in result.messages[0].content
    assert [m.content for m in result.messages[1:]] == ["new2", "latest"]


def test_trim_without_summary():
    messages = _msgs(("user", "a"), ("assistant", "b"), ("user", "c"))
    result = apply_context_window(
        messages,
        ContextConfig(max_messages=1, summarize_overflow=False),
    )
    assert result.dropped_count == 2
    assert result.summarized is False
    assert len(result.messages) == 1
    assert result.messages[0].content == "c"


def test_trim_by_max_chars():
    messages = _msgs(
        ("user", "x" * 50),
        ("assistant", "y" * 50),
        ("user", "short"),
    )
    result = apply_context_window(
        messages,
        ContextConfig(max_messages=0, max_chars=20, summarize_overflow=False),
    )
    assert result.dropped_count >= 1
    assert result.messages[-1].content == "short"
    assert sum(estimate_message_chars(m) for m in result.messages) <= 20 or len(result.messages) == 1


def test_does_not_split_tool_call_block():
    messages = [
        ChatMessage("user", "old"),
        ChatMessage("assistant", "ok", tool_calls=[{"id": "t1", "name": "remember", "arguments": {}}]),
        ChatMessage("tool", "saved", tool_call_id="t1"),
        ChatMessage("user", "now"),
    ]
    # Exactly 3: keep assistant + tool + latest user (not a bare tool at the start).
    result = apply_context_window(
        messages,
        ContextConfig(max_messages=3, summarize_overflow=False),
    )
    assert result.dropped_count == 1
    assert result.messages[0].tool_calls
    assert result.messages[1].role == "tool"
    assert result.messages[2].content == "now"

    # Budget 2 cannot fit the tool block; must not start on a tool message.
    result2 = apply_context_window(
        messages,
        ContextConfig(max_messages=2, summarize_overflow=False),
    )
    assert result2.messages[0].role != "tool"
    assert result2.messages[-1].content == "now"


def test_empty_history():
    result = apply_context_window([], ContextConfig(max_messages=10))
    assert result.messages == []
    assert result.dropped_count == 0
