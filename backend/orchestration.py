"""Chat turn orchestration: load chat + history, stream from model, persist messages, handle interrupt."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from backend.interfaces.model import ChatMessage, ChatRequest, ModelEventType
from backend.interfaces.tools import ToolContext
from backend.ws_schema import (
    build_done,
    build_error,
    build_reasoning,
    build_token,
    build_tool_call,
    build_tool_result,
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
    if t == ModelEventType.TOOL_CALL:
        return build_tool_call(
            p.get("tool_call_id", ""),
            p.get("name", ""),
            p.get("arguments") or {},
        )
    if t == ModelEventType.DONE:
        return build_done(stopped=p.get("stopped", False))
    if t == ModelEventType.ERROR:
        return build_error(p.get("message", ""), code=p.get("code"))
    return None


def _tools_to_openai(tools: list) -> list[dict[str, Any]]:
    """Convert Tool list to OpenAI-style tool definitions for ChatRequest."""
    out = []
    for t in tools:
        out.append({
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description,
                "parameters": t.args_schema(),
            },
        })
    return out


def _chat_message_from_dict(m: dict[str, Any]) -> ChatMessage:
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


async def _run_stream(
    ws,
    chat_id: str,
    user_content: str,
    *,
    chat_store,
    model_provider,
    config,
    memory_store=None,
    user_id: str | None = None,
    tools: list | None = None,
) -> None:
    """
    Run one assistant turn: append user message, stream model response to ws, persist assistant message.
    If memory_store and user_id are set, memories are injected as context. If tools are set, they are
    passed to the model and tool_call events are executed (e.g. remember); results are sent and the
    model is re-called until it returns no tool calls.
    Can be cancelled (asyncio.CancelledError); on cancel, persists partial assistant content and sends done(stopped=True).
    """
    chat = await chat_store.get_chat(chat_id)
    if not chat:
        await _send(ws, build_error("Chat not found", code="not_found"))
        return

    await chat_store.append_messages(chat_id, [{"role": "user", "content": user_content}])
    history = await chat_store.get_chat_messages(chat_id)

    messages = [
        _chat_message_from_dict(m)
        for m in history
        if isinstance(m.get("role"), str)
    ]

    # Prepend memories as context when memory_store and user_id are available
    if memory_store and user_id:
        memories = await memory_store.list_memories(user_id, chat_id=chat_id, limit=50)
        if memories:
            lines = [f"- {m.key}: {m.content}" for m in memories]
            memory_text = "Stored memories (use when relevant):\n" + "\n".join(lines)
            messages.insert(0, ChatMessage(role="system", content=memory_text))

    openai_tools = _tools_to_openai(tools) if tools else None
    tools_by_name = {t.name: t for t in (tools or [])}

    final_content: list[str] = []
    current_messages = list(messages)
    model_id = chat.model or config.model.default_model

    while True:
        request = ChatRequest(
            messages=current_messages,
            model=model_id,
            tools=openai_tools,
            tool_choice="auto" if openai_tools else None,
        )
        accumulated: list[str] = []
        tool_calls_this_turn: list[dict[str, Any]] = []

        try:
            async for event in model_provider.stream_chat(request):
                msg = _event_to_ws_message(event)
                if msg:
                    await _send(ws, msg)
                if event.type == ModelEventType.TOKEN:
                    accumulated.append(event.payload.get("text", ""))
                if event.type == ModelEventType.TOOL_CALL:
                    p = event.payload or {}
                    tool_calls_this_turn.append({
                        "id": p.get("tool_call_id", ""),
                        "name": p.get("name", ""),
                        "arguments": p.get("arguments") or {},
                    })
                if event.type == ModelEventType.DONE:
                    break
                if event.type == ModelEventType.ERROR:
                    break
        except asyncio.CancelledError:
            assistant_content = "".join(accumulated) + "".join(final_content)
            if assistant_content:
                await chat_store.append_messages(chat_id, [{"role": "assistant", "content": assistant_content}])
            await _send(ws, build_done(stopped=True))
            raise

        turn_content = "".join(accumulated)
        final_content.append(turn_content)

        if not tool_calls_this_turn:
            break

        # Execute each tool call and collect results
        context = ToolContext(
            user_id=user_id or config.app.default_user_id,
            chat_id=chat_id,
            memory_store=memory_store,
        )
        tool_results: list[tuple[str, str, bool]] = []  # (tool_call_id, content, success)
        for tc in tool_calls_this_turn:
            tool_id = tc.get("id", "")
            name = tc.get("name", "")
            args = tc.get("arguments") or {}
            if isinstance(args, str):
                try:
                    args = json.loads(args) if args else {}
                except json.JSONDecodeError:
                    args = {}
            tool = tools_by_name.get(name)
            if not tool:
                tool_results.append((tool_id, f"Unknown tool: {name}", False))
                await _send(ws, build_tool_result(tool_id, False, f"Unknown tool: {name}"))
                continue
            result = await tool.call(args, context)
            tool_results.append((tool_id, result.content, result.success))
            await _send(ws, build_tool_result(tool_id, result.success, result.content, data=result.data))

        # Append assistant message with tool_calls and tool result messages for next model call
        assistant_msg = ChatMessage(
            role="assistant",
            content=turn_content,
            tool_calls=[{"id": tc["id"], "name": tc["name"], "arguments": tc["arguments"]} for tc in tool_calls_this_turn],
            tool_call_id=None,
        )
        current_messages.append(assistant_msg)
        for tool_id, content, _ in tool_results:
            current_messages.append(ChatMessage(role="tool", content=content, tool_calls=None, tool_call_id=tool_id))

    assistant_content = "".join(final_content)
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
    memory_store=None,
    user_id: str | None = None,
    tools: list | None = None,
) -> None:
    """
    Run _run_stream in a task; store the task in stream_task_ref so the WS handler can cancel it on interrupt.
    """
    task = asyncio.create_task(
        _run_stream(
            ws,
            chat_id,
            user_content,
            chat_store=chat_store,
            model_provider=model_provider,
            config=config,
            memory_store=memory_store,
            user_id=user_id,
            tools=tools,
        ),
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
