"""OpenAI API model provider: chat streaming, embeddings, and model list."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from openai import AsyncOpenAI

from backend.interfaces.model import (
    ChatMessage,
    ChatRequest,
    ModelEvent,
    ModelEventType,
    ModelProvider,
)
from backend.config import PROVIDER_OPENAI


def _message_to_openai(m: ChatMessage) -> dict[str, Any]:
    out = {"role": m.role, "content": m.content or ""}
    if m.tool_calls:
        out["tool_calls"] = [
            {
                "id": tc.get("id", ""),
                "type": "function",
                "function": {
                    "name": tc.get("name", ""),
                    "arguments": json.dumps(tc.get("arguments") or {}) if isinstance(tc.get("arguments"), dict) else (tc.get("arguments") or "{}"),
                },
            }
            for tc in m.tool_calls
        ]
    if m.tool_call_id is not None:
        out["tool_call_id"] = m.tool_call_id
    return out


class OpenAIModelProvider(ModelProvider):
    """OpenAI API provider: stream_chat, embed, list_models."""

    name = PROVIDER_OPENAI

    def __init__(self, api_key: str | None = None, default_model: str = "gpt-5-mini"):
        self._client = AsyncOpenAI(api_key=api_key or None)  # None => use OPENAI_API_KEY env
        self._default_model = default_model

    async def stream_chat(self, request: ChatRequest) -> AsyncIterator[ModelEvent]:
        model = request.model or self._default_model
        messages = [_message_to_openai(m) for m in request.messages]
        # Omit temperature so API uses default; some models (e.g. o1) only support default (1).
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": True,
        }
        if request.max_tokens is not None:
            kwargs["max_tokens"] = request.max_tokens
        if request.tools:
            kwargs["tools"] = request.tools
        if request.tool_choice is not None:
            kwargs["tool_choice"] = request.tool_choice

        try:
            stream = await self._client.chat.completions.create(**kwargs)
            tool_calls_acc: list[dict[str, Any]] = []
            async for chunk in stream:
                choice = chunk.choices[0] if chunk.choices else None
                if not choice:
                    continue
                delta = choice.delta or {}

                if getattr(delta, "content", None):
                    yield ModelEvent(type=ModelEventType.TOKEN, payload={"text": delta.content})

                if getattr(delta, "tool_calls", None):
                    for tc in delta.tool_calls:
                        idx = getattr(tc, "index", None)
                        if idx is None:
                            idx = len(tool_calls_acc)
                        while len(tool_calls_acc) <= idx:
                            tool_calls_acc.append({"id": "", "name": "", "arguments": ""})
                        acc = tool_calls_acc[idx]
                        if getattr(tc, "id", None):
                            acc["id"] = tc.id
                        fn = getattr(tc, "function", None)
                        if fn:
                            if getattr(fn, "name", None):
                                acc["name"] = fn.name
                            if getattr(fn, "arguments", None):
                                acc["arguments"] = acc.get("arguments", "") + fn.arguments

                if getattr(choice, "finish_reason", None):
                    if choice.finish_reason == "tool_calls":
                        for acc in tool_calls_acc:
                            if acc.get("id") or acc.get("name"):
                                args = acc.get("arguments") or "{}"
                                try:
                                    args_parsed = json.loads(args) if args else {}
                                except json.JSONDecodeError:
                                    args_parsed = {}
                                yield ModelEvent(
                                    type=ModelEventType.TOOL_CALL,
                                    payload={
                                        "tool_call_id": acc.get("id", ""),
                                        "name": acc.get("name", ""),
                                        "arguments": args_parsed,
                                    },
                                )
                    yield ModelEvent(type=ModelEventType.DONE, payload={"stopped": False})
                    return

            yield ModelEvent(type=ModelEventType.DONE, payload={"stopped": False})
        except Exception as e:
            yield ModelEvent(type=ModelEventType.ERROR, payload={"message": str(e), "code": "provider_error"})

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        try:
            r = await self._client.embeddings.create(
                model="text-embedding-3-small",
                input=texts,
            )
            return [item.embedding for item in r.data]
        except Exception:
            return [[0.0] * 1536 for _ in texts]

    def list_models(self) -> list[dict[str, Any]]:
        return [
            {"id": "gpt-5.1", "provider": self.name, "context_length": 128000},
            {"id": "gpt-5-mini", "provider": self.name, "context_length": 128000},
            {"id": "gpt-5-nano", "provider": self.name, "context_length": 128000},
        ]
