"""Model provider interface and streaming event types."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, AsyncIterator, Protocol


class ModelEventType(StrEnum):
    """Event types streamed from ModelProvider to the client."""

    TOKEN = "token"
    REASONING = "reasoning"  # raw chain-of-thought / thinking
    TOOL_CALL = "tool_call"
    TOOL_PREVIEW = "tool_preview"
    TOOL_RESULT = "tool_result"
    METADATA = "metadata"
    DONE = "done"
    ERROR = "error"


@dataclass
class ModelEvent:
    """A single event in the model stream."""

    type: ModelEventType
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class ChatMessage:
    """A single message in a conversation (system, user, assistant, or tool)."""

    role: str  # "system" | "user" | "assistant" | "tool"
    content: str
    tool_calls: list[dict[str, Any]] | None = None  # assistant: [{id, name, arguments}]
    tool_call_id: str | None = None  # tool role: which call this result is for


@dataclass
class ChatRequest:
    """Input to ModelProvider.stream_chat."""

    messages: list[ChatMessage]
    model: str | None = None  # None = use default from config
    temperature: float = 0.7
    max_tokens: int | None = None
    tools: list[dict[str, Any]] | None = None  # OpenAI-style tool definitions
    tool_choice: str | None = None  # "auto" | "none" | {"type": "function", "function": {"name": "..."}}


class ModelProvider(Protocol):
    """Swappable LLM provider (OpenAI, local Ollama/vLLM, etc.)."""

    def stream_chat(self, request: ChatRequest) -> AsyncIterator[ModelEvent]:
        """Stream chat completion events (tokens, reasoning, tool calls, etc.)."""
        ...

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Return embedding vectors for the given texts."""
        ...

    def list_models(self) -> list[dict[str, Any]]:
        """Return available models (id, provider, context_length, etc.)."""
        ...
