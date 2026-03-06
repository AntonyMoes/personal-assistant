"""Tests for WebSocket route: send_message -> done, invalid JSON -> error, interrupt -> done(stopped)."""

import json
import pytest


@pytest.mark.asyncio
async def test_ws_send_message_returns_done(client):
    # Create a chat so send_message has a valid chat_id
    r = await client.post("/chats", json={"title": "Test"})
    assert r.status == 201
    chat_id = (await r.json())["id"]
    ws = await client.ws_connect(f"/ws/chats/{chat_id}")
    await ws.send_str(json.dumps({"type": "send_message", "payload": {"content": "hi"}}))
    # Stub provider streams tokens then done; consume until done
    done_msg = None
    while True:
        msg = await ws.receive()
        assert msg.type == 1
        data = json.loads(msg.data)
        if data["type"] == "done":
            done_msg = data
            break
        if data["type"] == "error":
            pytest.fail(f"Unexpected error: {data}")
    assert done_msg["payload"]["stopped"] is False
    await ws.close()


@pytest.mark.asyncio
async def test_ws_send_message_nonexistent_chat_returns_error(client):
    ws = await client.ws_connect("/ws/chats/nonexistent-chat-id")
    await ws.send_str(json.dumps({"type": "send_message", "payload": {"content": "hi"}}))
    msg = await ws.receive()
    assert msg.type == 1
    data = json.loads(msg.data)
    assert data["type"] == "error"
    assert data["payload"].get("code") == "not_found"
    await ws.close()


@pytest.mark.asyncio
async def test_ws_invalid_json_returns_error(client):
    ws = await client.ws_connect("/ws/chats/any")
    await ws.send_str("not json")
    msg = await ws.receive()
    assert msg.type == 1
    data = json.loads(msg.data)
    assert data["type"] == "error"
    assert data["payload"].get("code") == "invalid_message"
    await ws.close()


@pytest.mark.asyncio
async def test_ws_interrupt_returns_done_stopped(client):
    ws = await client.ws_connect("/ws/chats/any")
    await ws.send_str(json.dumps({"type": "interrupt", "payload": {}}))
    msg = await ws.receive()
    assert msg.type == 1
    data = json.loads(msg.data)
    assert data["type"] == "done"
    assert data["payload"]["stopped"] is True
    await ws.close()


@pytest.mark.asyncio
async def test_ws_permission_decision_returns_done(client):
    ws = await client.ws_connect("/ws/chats/any")
    await ws.send_str(json.dumps({
        "type": "permission_decision",
        "payload": {"tool_call_id": "c1", "approved": True},
    }))
    msg = await ws.receive()
    assert msg.type == 1
    data = json.loads(msg.data)
    assert data["type"] == "done"
    await ws.close()
