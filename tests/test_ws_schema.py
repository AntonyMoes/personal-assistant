"""Tests for backend.ws_schema: parse_client_message, build_* output shape."""

import pytest

from backend.ws_schema import (
    ClientMsgType,
    ServerMsgType,
    parse_client_message,
    build_send_message,
    build_permission_decision,
    build_interrupt,
    build_token,
    build_reasoning,
    build_tool_call,
    build_done,
    build_error,
    build_tool_preview,
    build_permission_request,
    build_tool_result,
    build_metadata,
    server_message,
)


# --- parse_client_message ---


def test_parse_client_message_send_message():
    data = {"type": "send_message", "payload": {"content": "hello"}}
    msg_type, payload = parse_client_message(data)
    assert msg_type == "send_message"
    assert payload == {"content": "hello"}


def test_parse_client_message_permission_decision():
    data = {"type": "permission_decision", "payload": {"tool_call_id": "abc", "approved": True}}
    msg_type, payload = parse_client_message(data)
    assert msg_type == "permission_decision"
    assert payload["tool_call_id"] == "abc"
    assert payload["approved"] is True


def test_parse_client_message_interrupt():
    data = {"type": "interrupt"}
    msg_type, payload = parse_client_message(data)
    assert msg_type == "interrupt"
    assert payload == {}


def test_parse_client_message_missing_type():
    with pytest.raises(ValueError, match="Missing 'type'"):
        parse_client_message({"payload": {}})


def test_parse_client_message_unknown_type():
    with pytest.raises(ValueError, match="Unknown client message type"):
        parse_client_message({"type": "unknown_kind", "payload": {}})


def test_parse_client_message_payload_default():
    data = {"type": "send_message"}
    _, payload = parse_client_message(data)
    assert payload == {}


def test_parse_client_message_payload_non_dict_coerced_to_empty():
    data = {"type": "interrupt", "payload": "x"}
    _, payload = parse_client_message(data)
    assert payload == {}


# --- build_* output shape ---


def test_build_send_message():
    out = build_send_message("hi")
    assert out == {"type": "send_message", "payload": {"content": "hi"}}


def test_build_permission_decision():
    out = build_permission_decision("call-1", True)
    assert out == {"type": "permission_decision", "payload": {"tool_call_id": "call-1", "approved": True}}


def test_build_interrupt():
    out = build_interrupt()
    assert out == {"type": "interrupt", "payload": {}}


def test_build_token():
    out = build_token("hello")
    assert out == {"type": "token", "payload": {"text": "hello"}}


def test_build_reasoning():
    out = build_reasoning("thinking...")
    assert out == {"type": "reasoning", "payload": {"text": "thinking..."}}


def test_build_tool_call():
    out = build_tool_call("id1", "search", {"q": "x"})
    assert out["type"] == "tool_call"
    assert out["payload"] == {"tool_call_id": "id1", "name": "search", "arguments": {"q": "x"}}


def test_build_done():
    assert build_done() == {"type": "done", "payload": {"stopped": False}}
    assert build_done(stopped=True) == {"type": "done", "payload": {"stopped": True}}


def test_build_error():
    out = build_error("failed", code="err1")
    assert out == {"type": "error", "payload": {"message": "failed", "code": "err1"}}
    out = build_error("failed")
    assert out["payload"]["code"] is None


def test_build_tool_preview():
    out = build_tool_preview(
        tool_call_id="c1",
        name="write",
        title="Write file",
        summary="Create foo.txt",
        affected_resources=["foo.txt"],
        arguments={"path": "foo.txt"},
        dry_run_result="would create foo.txt",
    )
    assert out["type"] == "tool_preview"
    p = out["payload"]
    assert p["tool_call_id"] == "c1"
    assert p["name"] == "write"
    assert p["title"] == "Write file"
    assert p["dry_run_result"] == "would create foo.txt"


def test_build_permission_request():
    out = build_permission_request(
        tool_call_id="c1", name="w", title="T", summary="S", affected_resources=[], arguments={}
    )
    assert out["type"] == "permission_request"
    assert out["payload"]["tool_call_id"] == "c1"


def test_build_tool_result():
    out = build_tool_result("c1", True, "ok", data={"n": 1})
    assert out["type"] == "tool_result"
    assert out["payload"] == {"tool_call_id": "c1", "success": True, "content": "ok", "data": {"n": 1}}


def test_build_metadata():
    out = build_metadata({"model": "gpt-4o", "tokens": 10})
    assert out == {"type": "metadata", "payload": {"model": "gpt-4o", "tokens": 10}}


def test_server_message_default_payload():
    out = server_message("custom")
    assert out == {"type": "custom", "payload": {}}
