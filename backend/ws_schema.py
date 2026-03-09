"""
WebSocket message schema for chat streaming.

All messages are JSON objects. Server and client use a common shape:
  { "type": "<message_type>", "payload": { ... } }

Payload is optional; omit or use {} when there are no extra fields.

--- Client → Server (incoming) ---

  send_message      Send a new user message; server will stream the assistant reply.
    payload: { "content": string }

  permission_decision   Response to a permission_request. Required to unblock the stream.
    payload: { "tool_call_id": string, "approved": boolean }
    tool_call_id must match permission_request.payload.tool_call_id.

  interrupt         Stop the current generation. Server will send done(stopped: true) and persist partial reply.
    payload: {} or omit

--- Server → Client (outgoing) ---

  token             One or more content tokens.
    payload: { "text": string }

  reasoning         Raw chain-of-thought / thinking (streamed).
    payload: { "text": string }

  tool_call          Model requested a tool (name + arguments). Followed by tool_preview or permission_request.
    payload: { "tool_call_id": string, "name": string, "arguments": object }
    tool_call_id: backend-generated id for this invocation; same value in tool_preview, permission_request, tool_result.

  tool_preview       Human-readable preview of the proposed tool action (always sent before execution).
    payload: {
      "tool_call_id": string,
      "name": string,
      "title": string,
      "summary": string,
      "affected_resources": string[],
      "dry_run_result": string | null,
      "arguments": object
    }

  permission_request   Same as tool_preview; backend is waiting for permission_decision with this tool_call_id.
    payload: same as tool_preview.

  tool_result       Result of executing a tool (after approval or auto-allow).
    payload: { "tool_call_id": string, "success": boolean, "content": string, "data": object | null }
    tool_call_id: same as the originating tool_call.

  memory_created    Emitted when the remember tool successfully saves a memory (no confirmation needed).
    payload: { "id": string, "key": string, "content": string }

  metadata          Optional server-supplied info. Payload shape is app-specific.
    payload: { ... } (arbitrary)

  done              Generation finished. Stream is complete for this turn.
    payload: { "stopped": boolean }  -- stopped true if user sent interrupt
    payload: {} if completed normally

  error             An error occurred; stream ends.
    payload: { "message": string, "code": string | null }
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any


# --- Client → Server ---


class ClientMsgType(StrEnum):
    SEND_MESSAGE = "send_message"
    PERMISSION_DECISION = "permission_decision"
    INTERRUPT = "interrupt"


def parse_client_message(data: dict[str, Any]) -> tuple[ClientMsgType, dict[str, Any]]:
    """
    Parse a client message. Returns (type, payload).
    Raises ValueError if type is missing or unknown.
    """
    msg_type = data.get("type")
    if not msg_type:
        raise ValueError("Missing 'type' in message")
    if msg_type not in (t.value for t in ClientMsgType):
        raise ValueError(f"Unknown client message type: {msg_type!r}")
    payload = data.get("payload", {})
    return ClientMsgType(msg_type), payload if isinstance(payload, dict) else {}


def build_send_message(content: str) -> dict[str, Any]:
    return {"type": ClientMsgType.SEND_MESSAGE.value, "payload": {"content": content}}


def build_permission_decision(tool_call_id: str, approved: bool) -> dict[str, Any]:
    return {
        "type": ClientMsgType.PERMISSION_DECISION.value,
        "payload": {"tool_call_id": tool_call_id, "approved": approved},
    }


def build_interrupt() -> dict[str, Any]:
    return {"type": ClientMsgType.INTERRUPT.value, "payload": {}}


# --- Server → Client ---


class ServerMsgType(StrEnum):
    TOKEN = "token"
    REASONING = "reasoning"
    TOOL_CALL = "tool_call"
    TOOL_PREVIEW = "tool_preview"
    PERMISSION_REQUEST = "permission_request"
    TOOL_RESULT = "tool_result"
    MEMORY_CREATED = "memory_created"
    MEMORY_UPDATED = "memory_updated"
    MEMORY_DELETED = "memory_deleted"
    METADATA = "metadata"
    DONE = "done"
    ERROR = "error"


def server_message(msg_type: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build a server message. payload defaults to {}."""
    return {"type": msg_type, "payload": payload if payload is not None else {}}


def build_token(text: str) -> dict[str, Any]:
    return server_message(ServerMsgType.TOKEN.value, {"text": text})


def build_reasoning(text: str) -> dict[str, Any]:
    return server_message(ServerMsgType.REASONING.value, {"text": text})


def build_tool_call(tool_call_id: str, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    return server_message(
        ServerMsgType.TOOL_CALL.value,
        {"tool_call_id": tool_call_id, "name": name, "arguments": arguments},
    )


def build_tool_preview(
    tool_call_id: str,
    name: str,
    title: str,
    summary: str,
    affected_resources: list[str],
    arguments: dict[str, Any],
    dry_run_result: str | None = None,
) -> dict[str, Any]:
    return server_message(
        ServerMsgType.TOOL_PREVIEW.value,
        {
            "tool_call_id": tool_call_id,
            "name": name,
            "title": title,
            "summary": summary,
            "affected_resources": affected_resources,
            "dry_run_result": dry_run_result,
            "arguments": arguments,
        },
    )


def build_permission_request(
    tool_call_id: str,
    name: str,
    title: str,
    summary: str,
    affected_resources: list[str],
    arguments: dict[str, Any],
    dry_run_result: str | None = None,
) -> dict[str, Any]:
    """Same payload as tool_preview; use when backend is waiting for permission_decision."""
    return server_message(
        ServerMsgType.PERMISSION_REQUEST.value,
        {
            "tool_call_id": tool_call_id,
            "name": name,
            "title": title,
            "summary": summary,
            "affected_resources": affected_resources,
            "dry_run_result": dry_run_result,
            "arguments": arguments,
        },
    )


def build_tool_result(
    tool_call_id: str,
    success: bool,
    content: str,
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return server_message(
        ServerMsgType.TOOL_RESULT.value,
        {"tool_call_id": tool_call_id, "success": success, "content": content, "data": data},
    )


def build_memory_created(memory_id: str, key: str, content: str) -> dict[str, Any]:
    """Emitted when the remember tool creates a memory; frontend can show a message with delete."""
    return server_message(
        ServerMsgType.MEMORY_CREATED.value,
        {"id": memory_id, "key": key, "content": content},
    )


def build_memory_updated(
    memory_id: str, key: str, old_content: str, new_content: str
) -> dict[str, Any]:
    """Emitted when the remember tool updates an existing memory; frontend can show Roll back."""
    return server_message(
        ServerMsgType.MEMORY_UPDATED.value,
        {"id": memory_id, "key": key, "old_content": old_content, "new_content": new_content},
    )


def build_memory_deleted(memory_id: str, key: str, content: str) -> dict[str, Any]:
    """Emitted when the forget tool deletes a memory; frontend can show Roll back to recreate."""
    return server_message(
        ServerMsgType.MEMORY_DELETED.value,
        {"id": memory_id, "key": key, "content": content},
    )


def build_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    return server_message(ServerMsgType.METADATA.value, metadata)


def build_done(stopped: bool = False) -> dict[str, Any]:
    return server_message(ServerMsgType.DONE.value, {"stopped": stopped})


def build_error(message: str, code: str | None = None) -> dict[str, Any]:
    return server_message(ServerMsgType.ERROR.value, {"message": message, "code": code})
