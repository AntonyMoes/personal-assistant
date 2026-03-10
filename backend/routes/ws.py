"""WebSocket endpoint for chat streaming (tokens, reasoning, tool previews, etc.)."""

import json
from aiohttp import web, WSMessage

from backend.interfaces import ChatStore
from backend.orchestration import run_stream_with_interrupt
from backend.utils import WSChannel
from backend.ws_schema import build_done, build_error, parse_client_message, ClientMsgType


# todo redo this to creating a worker (if there's none) and communicating with him through async queues
async def chat_ws(request: web.Request) -> web.StreamResponse:
    """WebSocket handler for a single chat. chat_id in path or query."""
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    channel = WSChannel(ws)
    chat_id = request.match_info.get("chat_id") or request.query.get("chat_id", "")
    app = request.app
    chat_store: ChatStore = app["chat_store"]
    model_provider = app["model_provider"]
    config = app["config"]

    # Active stream task for this connection; interrupt cancels it
    active_stream: list = []  # todo: atrocity

    responses_in_progress = await chat_store.get_responses_in_progress(chat_id)
    for response in responses_in_progress:
        ...  # todo: run through... well. this needs to be done with queues and workers
        await run_stream_with_interrupt(
            channel,
            chat_id,
            response,
            chat_store=chat_store,
            model_provider=model_provider,
            config=config,
            stream_task_ref=active_stream,
            memory_store=app.get("memory_store"),
            user_id=config.app.default_user_id,
            tools=app.get("tools") or [],
            embedding_store=app.get("embedding_store"),
            permission_store=app.get("permission_store"),
        )

    try:
        async for msg in channel:
            if msg.type == web.WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                    msg_type, payload = parse_client_message(data)
                    if msg_type == ClientMsgType.SEND_MESSAGE:
                        content = (payload.get("content") or "").strip()
                        if not content:
                            await channel.send(build_error("Empty message content", code="invalid_message"))
                            continue
                        # todo this way active streams can't be cancelled
                        await run_stream_with_interrupt(
                            channel,
                            chat_id,
                            content,
                            chat_store=chat_store,
                            model_provider=model_provider,
                            config=config,
                            stream_task_ref=active_stream,
                            memory_store=app.get("memory_store"),
                            user_id=config.app.default_user_id,
                            tools=app.get("tools") or [],
                            embedding_store=app.get("embedding_store"),
                            permission_store=app.get("permission_store"),
                        )
                    elif msg_type == ClientMsgType.PERMISSION_DECISION:
                        chat_record = await chat_store.get_chat(chat_id)
                        if not chat_record:
                            await channel.send(build_error(f"Permission decision for a missing chat: {chat_id}",
                                                           code="invalid_message"))
                            continue

                        tool_call_id = payload.get("tool_call_id")
                        approved = payload.get("approved")
                        if tool_call_id is None or approved is None:
                            await channel.send(build_error(f"Missing tool_call_id or approved", code="invalid_message"))
                            continue

                        tool_call = next((
                            tc
                            for r in chat_record.responses
                            for tc in r.pending_tool_calls
                            if tc.id == tool_call_id
                        ), None)
                        if tool_call is None:
                            await channel.send(
                                build_error(f"No responses with tool_call_id {tool_call_id}", code="invalid_message"))
                            continue

                        response = (next((r for r in chat_record.responses if tool_call in r.pending_tool_calls)))
                        tool_call.permission = approved
                        await chat_store.set_response_in_progress(chat_id, response.id, response)

                        await run_stream_with_interrupt(
                            channel,
                            chat_id,
                            response,
                            chat_store=chat_store,
                            model_provider=model_provider,
                            config=config,
                            stream_task_ref=active_stream,
                            memory_store=app.get("memory_store"),
                            user_id=config.app.default_user_id,
                            tools=app.get("tools") or [],
                            embedding_store=app.get("embedding_store"),
                            permission_store=app.get("permission_store"),
                        )
                    elif msg_type == ClientMsgType.INTERRUPT:
                        # todo remove response in progress
                        if active_stream:
                            task = active_stream[0]
                            task.cancel()
                            try:
                                await task
                            except Exception:
                                pass
                        else:
                            await channel.send(build_done(stopped=True))
                except (json.JSONDecodeError, ValueError) as e:
                    await channel.send(build_error(str(e), code="invalid_message"))
            elif msg.type == web.WSMsgType.ERROR:
                break
    except Exception as e:
        print(e)
    finally:
        if active_stream:
            active_stream[0].cancel()
            try:
                await active_stream[0]
            except Exception:
                pass
        await ws.close()
    return ws


def setup_ws_routes(app: web.Application) -> None:
    """Register WebSocket routes."""
    app.router.add_get("/ws/chats/{chat_id}", chat_ws)
