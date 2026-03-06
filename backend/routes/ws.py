"""WebSocket endpoint for chat streaming (tokens, reasoning, tool previews, etc.)."""

import json
from aiohttp import web

# TODO: define message schema (client -> server: send_message, permission_decision;
#       server -> client: token, reasoning, tool_preview, permission_request, tool_result, done)


async def chat_ws(request: web.Request) -> web.StreamResponse:
    """WebSocket handler for a single chat. chat_id in path or query."""
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    chat_id = request.match_info.get("chat_id") or request.query.get("chat_id", "")
    # TODO: load chat, validate, attach ModelProvider + ChatStore; stream events
    try:
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                data = json.loads(msg.data)
                # Echo placeholder until orchestration is implemented
                await ws.send_str(json.dumps({"type": "done", "payload": {}}))
            elif msg.type == web.WSMsgType.ERROR:
                break
    finally:
        await ws.close()
    return ws


def setup_ws_routes(app: web.Application) -> None:
    """Register WebSocket routes."""
    app.router.add_get("/ws/chats/{chat_id}", chat_ws)
