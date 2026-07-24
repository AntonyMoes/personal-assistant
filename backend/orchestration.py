"""Chat turn orchestration: load chat + history, stream from model, persist messages, handle interrupt."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any

from backend.interfaces import ModelProvider, ToolResult, ChatStore
from backend.interfaces.model import ChatMessage, ChatRequest, ModelEventType, ModelEvent
from backend.interfaces.storage import ResponseInProgressRecord, PendingToolCall, PermissionStore
from backend.interfaces.tools import ToolContext, Tool, Permission
from backend.tools import RememberTool, ForgetTool
from backend.utils import WSChannel
from backend.ws_schema import (
    build_done,
    build_error,
    build_memory_created,
    build_memory_deleted,
    build_memory_updated,
    build_reasoning,
    build_token,
    build_tool_call,
    build_tool_result,
    build_permission_request,
)


@dataclass
class ToolCall:
    name: str
    call_id: str
    args: dict

    def __init__(self, name: str, call_id: str, args: dict | str):
        self.name = name
        self.call_id = call_id

        if isinstance(args, str):
            try:
                actual_args = json.loads(args) if args else {}
            except json.JSONDecodeError:
                actual_args = {}
        else:
            actual_args = args
        self.args = actual_args


def _event_to_ws_message(event: ModelEvent) -> dict[str, Any] | None:
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


async def _get_call_permission(
        channel: WSChannel,
        tool: Tool,
        tool_call: ToolCall,
        tool_context: ToolContext,
        permission_store: PermissionStore | None,
) -> bool | None:
    # Resolve permission for this tool based on its capabilities for this call and global settings.
    # TODO: support ASK_ONCE_PER_CHAT with per-chat caching; for now it behaves like ASK.
    permission = Permission.ASK
    if permission_store:
        try:
            caps = tool.capabilities(tool_call.args)
        except Exception:
            caps = []
        perms: list[Permission] = []
        for cap in caps:
            try:
                cap_perm = await permission_store.get(cap)
            except Exception:
                cap_perm = Permission.ASK
            perms.append(cap_perm)
        if perms:
            if Permission.DENY in perms:
                permission = Permission.DENY
            elif Permission.ASK in perms:
                permission = Permission.ASK
            elif Permission.ASK_ONCE_PER_CHAT in perms:
                permission = Permission.ASK_ONCE_PER_CHAT
            else:
                permission = Permission.ALLOW
    if permission is Permission.ALLOW:
        return True

    if permission is Permission.DENY:
        return False

    if permission is Permission.ASK or permission is Permission.ASK_ONCE_PER_CHAT:
        preview = await tool.preview(tool_call.args, tool_context)
        permission_request = build_permission_request(
            tool_call.call_id,
            tool_call.name,
            preview.title,
            preview.summary,
            preview.affected_resources,
            preview.arguments,
            preview.dry_run_result
        )
        await channel.send(permission_request)
        return None

    return False


def _try_get_memory_message(call: ToolCall, result: ToolResult) -> dict | None:
    if call.name == RememberTool.NAME and result.success and result.data:
        data = result.data or {}
        mem_id = data.get("id")
        mem_key = data.get("key")
        mem_content = data.get("content", "")
        if mem_id is not None and mem_id != "":
            if data.get("created", True):
                return build_memory_created(
                    str(mem_id),
                    str(mem_key) if mem_key is not None else "",
                    str(mem_content) if mem_content is not None else "",
                )
            else:
                old = data.get("previous_content", "")
                return build_memory_updated(
                    str(mem_id),
                    str(mem_key) if mem_key is not None else "",
                    str(old) if old is not None else "",
                    str(mem_content) if mem_content is not None else "",
                )
    elif call.name == ForgetTool.NAME and result.success and result.data:
        data = result.data or {}
        mem_id = data.get("id")
        mem_key = data.get("key")
        mem_content = data.get("content", "")
        if mem_id is not None and mem_key is not None:
            return build_memory_deleted(
                str(mem_id),
                str(mem_key),
                str(mem_content) if mem_content is not None else "",
            )

    return None


async def _run_stream(
        channel: WSChannel,
        chat_id: str,
        user_content: str | ResponseInProgressRecord,
        *,
        chat_store: ChatStore,
        model_provider: ModelProvider,
        config,
        memory_store=None,
        user_id: str | None = None,
        tools: list[Tool] | None = None,
        embedding_store=None,
        permission_store: PermissionStore | None = None,
) -> None:
    """
    Run one assistant turn: append user message, stream model response to ws, persist assistant message.
    Injects config.app.system_prompt (if set), then memories, as ephemeral system messages.
    If tools are set, they are passed to the model and tool_call events are executed; results are
    sent and the model is re-called until it returns no tool calls.
    Can be cancelled (asyncio.CancelledError); on cancel, persists partial assistant content and sends done(stopped=True).
    """
    chat = await chat_store.get_chat(chat_id)
    if not chat:
        await channel.send(build_error("Chat not found", code="not_found"))
        return

    if isinstance(user_content, str):
        await chat_store.append_messages(chat_id, [ChatMessage("user", user_content)])
    history_with_memories = await chat_store.get_chat_messages(chat_id)

    # Prepend stable system prompt, then global memories (not persisted into chat history).
    prefix: list[ChatMessage] = []
    system_prompt = (getattr(getattr(config, "app", None), "system_prompt", None) or "").strip()
    if system_prompt:
        prefix.append(ChatMessage(role="system", content=system_prompt))
    if memory_store and user_id:
        memories = await memory_store.list_memories(user_id, limit=50)
        if memories:
            lines = [f"- {m.key}: {m.content}" for m in memories]
            memory_text = "Stored memories (use when relevant):\n" + "\n".join(lines)
            prefix.append(ChatMessage(role="system", content=memory_text))
    if prefix:
        history_with_memories = prefix + history_with_memories

    openai_tools = _tools_to_openai(tools) if tools else None
    tools_by_name: dict[str, Tool] = {t.name: t for t in (tools or [])}
    model_id = chat.model or config.model.default_model

    response_record = user_content if isinstance(user_content, ResponseInProgressRecord) \
        else await chat_store.create_response_in_progress(chat_id)

    final_content = response_record.pending_content
    pending_tool_calls: list[tuple[ToolCall, bool | None]] = [  # tool_call, permission
        (ToolCall(tc.tool_name, tc.id, tc.args), tc.permission) for tc in response_record.pending_tool_calls
    ]
    response_record.pending_tool_calls.clear()
    await chat_store.set_response_in_progress(chat_id, response_record.id, response_record)

    all_tool_calls = pending_tool_calls
    while True:
        no_pending_tool_calls = not response_record.pending_tool_calls and not all_tool_calls
        tool_calls_this_turn: list[ToolCall] = []
        turn_content = ""
        if no_pending_tool_calls:
            context_messages = history_with_memories + response_record.internal_messages_context
            request = ChatRequest(
                messages=context_messages,
                model=model_id,
                tools=openai_tools,
                tool_choice="auto" if openai_tools else None,
            )

            # todo handle closing in-progress chats
            try:
                async for event in model_provider.stream_chat(request):
                    msg = _event_to_ws_message(event)
                    if msg:
                        await channel.send(msg)

                    if event.type == ModelEventType.TOKEN:
                        turn_content += event.payload.get("text", "")
                    elif event.type == ModelEventType.TOOL_CALL:
                        p = event.payload or {}
                        tool_calls_this_turn.append(ToolCall(
                            p.get("name", ""),
                            p.get("tool_call_id", ""),
                            p.get("arguments") or {}
                        ))
                    elif event.type == ModelEventType.DONE:
                        break
                    elif event.type == ModelEventType.ERROR:
                        break
            except asyncio.CancelledError:
                assistant_content = turn_content + final_content
                if assistant_content:
                    await chat_store.append_messages(chat_id, [ChatMessage("assistant", assistant_content)])
                await channel.send(build_done(stopped=True))
                raise

            final_content += turn_content

        all_tool_calls += [(tc, None) for tc in tool_calls_this_turn]
        if not all_tool_calls:
            break

        # Execute each tool call and collect results
        context = ToolContext(
            user_id=user_id or config.app.default_user_id,
            chat_id=chat_id,
            memory_store=memory_store,
            embedding_store=embedding_store,
            embedder=model_provider.embed
        )
        tool_results: list[tuple[str, str, bool]] = []  # (tool_call_id, content, success)
        for (tool_call, permission) in all_tool_calls:
            tool = tools_by_name.get(tool_call.name)
            if not tool:
                message = f"Unknown tool: {tool_call.name}"
                tool_results.append((tool_call.call_id, message, False))
                await channel.send(build_tool_result(tool_call.call_id, False, message))
                continue

            if permission is None:
                permission = await _get_call_permission(channel, tool, tool_call, context, permission_store)
            if permission is None:
                response_record.pending_tool_calls.append(PendingToolCall(tool_call.call_id, tool.name, tool_call.args))
                await chat_store.set_response_in_progress(chat_id, response_record.id, response_record)
                continue

            if permission:
                result = await tool.call(tool_call.args, context)
                tool_results.append((tool_call.call_id, result.content, result.success))
                await channel.send(build_tool_result(tool_call.call_id, result.success, result.content, data=result.data))

                memory_message = _try_get_memory_message(tool_call, result)
                if memory_message is not None:
                    await channel.send(memory_message)
            else:
                message = f"Permission to use tool {tool_call.name} with args {tool_call.args} was denied"
                tool_results.append((tool_call.call_id, message, False))
                await channel.send(build_tool_result(tool_call.call_id, False, message))
        all_tool_calls.clear()

        tool_messages = []
        if tool_calls_this_turn:
            # Append assistant message with tool_calls and tool result messages for next model call
            assistant_msg = ChatMessage(
                role="assistant",
                content=turn_content,
                tool_calls=[{"id": tc.call_id, "name": tc.name, "arguments": tc.args} for tc in tool_calls_this_turn]
            )
            tool_messages.append(assistant_msg)
        for tool_id, content, _ in tool_results:
            tool_messages.append(ChatMessage("tool", content, tool_call_id=tool_id))

        response_record.internal_messages_context += tool_messages
        await chat_store.set_response_in_progress(chat_id, response_record.id, response_record)

    if not response_record.pending_tool_calls:
        if final_content:
            await chat_store.append_messages(chat_id, [ChatMessage("assistant", final_content)])
        await chat_store.set_response_in_progress(chat_id, response_record.id, None)
    else:
        response_record.pending_content = final_content
        await chat_store.set_response_in_progress(chat_id, response_record.id, response_record)


async def run_stream_with_interrupt(
        channel: WSChannel,
        chat_id: str,
        user_content: str | ResponseInProgressRecord,
        *,
        chat_store: ChatStore,
        model_provider: ModelProvider,
        config,
        stream_task_ref: list,
        memory_store=None,
        user_id: str | None = None,
        tools: list[Tool] | None = None,
        embedding_store=None,
        permission_store: PermissionStore | None = None,
) -> None:
    """
    Run _run_stream in a task; store the task in stream_task_ref so the WS handler can cancel it on interrupt.
    """
    task = asyncio.create_task(
        _run_stream(
            channel,
            chat_id,
            user_content,
            chat_store=chat_store,
            model_provider=model_provider,
            config=config,
            memory_store=memory_store,
            user_id=user_id,
            tools=tools,
            embedding_store=embedding_store,
            permission_store=permission_store,
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
