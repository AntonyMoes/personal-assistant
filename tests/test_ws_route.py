"""Tests for WebSocket route: send_message -> done, invalid JSON -> error, interrupt -> done(stopped)."""

import json
import pytest


@pytest.mark.asyncio
async def test_ws_send_message_returns_done(client):
    ws = await client.ws_connect("/ws/chats/test-chat-id")
    await ws.send_str(json.dumps({"type": "send_message", "payload": {"content": "hi"}}))
    msg = await ws.receive()
    assert msg.type == 1  # WSMsgType.TEXT
    data = json.loads(msg.data)
    assert data["type"] == "done"
    assert data["payload"]["stopped"] is False
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
