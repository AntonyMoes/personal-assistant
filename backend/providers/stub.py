"""Stub ModelProvider for development and testing. Streams a fixed response with no API calls."""

from __future__ import annotations

from collections.abc import AsyncIterator

from backend.interfaces.model import (
    ChatMessage,
    ChatRequest,
    ModelEvent,
    ModelEventType,
)
from backend.config import PROVIDER_STUB


class StubModelProvider:
    """Yields a simple token stream then done. No tools, no real LLM."""

    name = PROVIDER_STUB

    async def stream_chat(self, request: ChatRequest) -> AsyncIterator[ModelEvent]:
        # Echo a short response regardless of input
        reply = "I received your message. (Stub provider; no model connected.)"
        for chunk in [reply[i : i + 5] for i in range(0, len(reply), 5)]:
            yield ModelEvent(type=ModelEventType.TOKEN, payload={"text": chunk})
        yield ModelEvent(type=ModelEventType.DONE, payload={"stopped": False})

    async def embed(self, texts: list[str]) -> list[list[float]]:
        # Return zero vectors of fixed length
        dim = 8
        return [[0.0] * dim for _ in texts]

    def list_models(self) -> list[dict]:
        return [
            {"id": self.name, "provider": self.name, "context_length": 4096},
        ]
