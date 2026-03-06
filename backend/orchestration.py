"""Chat turn orchestration: load chat + history, stream from model, persist messages, handle interrupt."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from backend.interfaces.model import ChatMessage, ChatRequest, ModelEventType
from backend.ws_schema import (
    build_done,
    build_error,
    build_reasoning,
    build_token,
)


async def _send(ws, msg: dict) -> None:
    await ws.send_str(json.dumps(msg))


def _event_to_ws_message(event) -> dict[str, Any] | None:
    """Map ModelEvent to WS message dict. Returns None if event should be skipped."""
    t = event.type
    p = event.payload or {}
    if t == ModelEventType.TOKEN:
        return build_token(p.get("text", ""))
    if t == ModelEventType.REASONING:
        return build_reasoning(p.get("text", ""))
    if t == ModelEventType.DONE:
        return build_done(stopped=p.get("stopped", False))
    if t == ModelEventType.ERROR:
        return build_error(p.get("message", ""), code=p.get("code"))
    # Tool events (tool_call, tool_preview, tool_result, metadata) can be added when tools are wired
    return None


async def _run_stream(
    ws,
    chat_id: str,
    user_content: str,
    *,
    chat_store,
    model_provider,
    config,
) -> None:
    """
    Run one assistant turn: append user message, stream model response to ws, persist assistant message.
    Can be cancelled (asyncio.CancelledError); on cancel, persists partial assistant content and sends done(stopped=True).
    """
    # Validate chat exists before appending
    chat = await chat_store.get_chat(chat_id)
    if not chat:
        await _send(ws, build_error("Chat not found", code="not_found"))
        return

    await chat_store.append_messages(chat_id, [{"role": "user", "content": user_content}])
    history = await chat_store.get_chat_messages(chat_id)

    messages = [
        ChatMessage(role=m["role"], content=m["content"])
        for m in history
        if isinstance(m.get("role"), str) and isinstance(m.get("content"), str)
    ]
    request = ChatRequest(
        messages=messages,
        model=chat.model or config.model.default_model,
    )

    accumulated: list[str] = []

    try:
        async for event in model_provider.stream_chat(request):
            msg = _event_to_ws_message(event)
            if msg:
                await _send(ws, msg)
            if event.type == ModelEventType.TOKEN:
                accumulated.append(event.payload.get("text", ""))
            if event.type == ModelEventType.DONE:
                break
            if event.type == ModelEventType.ERROR:
                break
    except asyncio.CancelledError:
        assistant_content = "".join(accumulated)
        if assistant_content:
            await chat_store.append_messages(chat_id, [{"role": "assistant", "content": assistant_content}])
        await _send(ws, build_done(stopped=True))
        raise

    assistant_content = "".join(accumulated)
    if assistant_content:
        await chat_store.append_messages(chat_id, [{"role": "assistant", "content": assistant_content}])


async def run_stream_with_interrupt(
    ws,
    chat_id: str,
    user_content: str,
    *,
    chat_store,
    model_provider,
    config,
    stream_task_ref: list,
) -> None:
    """
    Run run_stream in a task; store the task in stream_task_ref so the WS handler can cancel it on interrupt.
    """
    task = asyncio.create_task(
        _run_stream(ws, chat_id, user_content, chat_store=chat_store, model_provider=model_provider, config=config),
    )
    stream_task_ref.append(task)
    try:
        await task
    except asyncio.CancelledError:
        # Interrupt: persist partial is done inside run_stream when it gets CancelledError
        pass
    finally:
        if stream_task_ref and stream_task_ref[0] is task:
            stream_task_ref.clear()
