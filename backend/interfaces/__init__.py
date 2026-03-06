"""Abstract interfaces for models, storage, and tools. Implementations are swappable."""

from backend.interfaces.model import (
    ChatMessage,
    ChatRequest,
    ModelEvent,
    ModelEventType,
    ModelProvider,
)
from backend.interfaces.storage import (
    ChatRecord,
    ChatStore,
    EmbeddingStore,
    MemoryRecord,
    MemoryStore,
)
from backend.interfaces.tools import (
    Capability,
    Tool,
    ToolContext,
    ToolPreview,
    ToolResult,
)

__all__ = [
    "ChatMessage",
    "ChatRequest",
    "ModelEvent",
    "ModelEventType",
    "ModelProvider",
    "ChatRecord",
    "ChatStore",
    "EmbeddingStore",
    "MemoryRecord",
    "MemoryStore",
    "Capability",
    "Tool",
    "ToolContext",
    "ToolPreview",
    "ToolResult",
]
