"""WebSocket endpoint for chat streaming (tokens, reasoning, tool previews, etc.)."""

import json
from aiohttp import web

from backend.orchestration import run_stream_with_interrupt
from backend.ws_schema import build_done, build_error, parse_client_message


async def chat_ws(request: web.Request) -> web.StreamResponse:
    """WebSocket handler for a single chat. chat_id in path or query."""
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    chat_id = request.match_info.get("chat_id") or request.query.get("chat_id", "")
    app = request.app
    chat_store = app["chat_store"]
    model_provider = app["model_provider"]
    config = app["config"]

    # Active stream task for this connection; interrupt cancels it
    active_stream: list = []

    try:
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                    msg_type, payload = parse_client_message(data)
                    if msg_type == "send_message":
                        content = (payload.get("content") or "").strip()
                        if not content:
                            await _send(ws, build_error("Empty message content", code="invalid_message"))
                            continue
                        await run_stream_with_interrupt(
                            ws,
                            chat_id,
                            content,
                            chat_store=chat_store,
                            model_provider=model_provider,
                            config=config,
                            stream_task_ref=active_stream,
                        )
                    elif msg_type == "permission_decision":
                        # No tools yet; ack only
                        await _send(ws, build_done())
                    elif msg_type == "interrupt":
                        if active_stream:
                            task = active_stream[0]
                            task.cancel()
                            try:
                                await task
                            except Exception:
                                pass
                        else:
                            await _send(ws, build_done(stopped=True))
                except (json.JSONDecodeError, ValueError) as e:
                    await _send(ws, build_error(str(e), code="invalid_message"))
            elif msg.type == web.WSMsgType.ERROR:
                break
    finally:
        if active_stream:
            active_stream[0].cancel()
            try:
                await active_stream[0]
            except Exception:
                pass
        await ws.close()
    return ws


async def _send(ws: web.WebSocketResponse, msg: dict) -> None:
    """Send a server message as JSON."""
    await ws.send_str(json.dumps(msg))


def setup_ws_routes(app: web.Application) -> None:
    """Register WebSocket routes."""
    app.router.add_get("/ws/chats/{chat_id}", chat_ws)
