"""WebSocket endpoint for chat streaming (tokens, reasoning, tool previews, etc.)."""

import json
from aiohttp import web

from backend.ws_schema import build_done, build_error, parse_client_message


async def chat_ws(request: web.Request) -> web.StreamResponse:
    """WebSocket handler for a single chat. chat_id in path or query."""
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    chat_id = request.match_info.get("chat_id") or request.query.get("chat_id", "")
    # TODO: load chat, validate, attach ModelProvider + ChatStore; stream events
    try:
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                    msg_type, payload = parse_client_message(data)
                    if msg_type == "send_message":
                        # Placeholder: no orchestration yet; just ack done
                        await _send(ws, build_done())
                    elif msg_type == "permission_decision":
                        # TODO: resolve pending permission, continue stream
                        await _send(ws, build_done())
                    elif msg_type == "interrupt":
                        # TODO: cancel stream, persist partial, send done(stopped=True)
                        await _send(ws, build_done(stopped=True))
                except (json.JSONDecodeError, ValueError) as e:
                    await _send(ws, build_error(str(e), code="invalid_message"))
            elif msg.type == web.WSMsgType.ERROR:
                break
    finally:
        await ws.close()
    return ws


async def _send(ws: web.WebSocketResponse, msg: dict) -> None:
    """Send a server message as JSON."""
    await ws.send_str(json.dumps(msg))


def setup_ws_routes(app: web.Application) -> None:
    """Register WebSocket routes."""
    app.router.add_get("/ws/chats/{chat_id}", chat_ws)
