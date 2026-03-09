from typing import Any

from backend.interfaces import ChatMessage


def chat_message_from_dict(m: dict[str, Any]) -> ChatMessage:
    """Build ChatMessage from stored dict (role, content; optional tool_calls, tool_call_id)."""
    content = m.get("content")
    if not isinstance(content, str):
        content = ""
    return ChatMessage(
        role=m["role"],
        content=content,
        tool_calls=m.get("tool_calls"),
        tool_call_id=m.get("tool_call_id"),
    )


def chat_message_to_dict(m: ChatMessage) -> dict[str, Any]:
    message_dict: dict[str, Any] = {
        "role": m.role,
        "content": m.content
    }
    if m.tool_calls:
        message_dict["tool_calls"] = m.tool_calls
    if m.tool_call_id:
        message_dict["tool_call_id"] = m.tool_call_id

    return message_dict