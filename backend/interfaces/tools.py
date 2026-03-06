"""Tool interface, capabilities, and preview-before-execute types."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol


class Capability(StrEnum):
    """Permission capability tags; each tool declares which it uses."""

    FILESYSTEM_READ = "filesystem_read"
    FILESYSTEM_WRITE = "filesystem_write"
    WEB_SEARCH = "web_search"
    OBSIDIAN_READ = "obsidian_read"
    OBSIDIAN_MODIFY = "obsidian_modify"


@dataclass
class ToolPreview:
    """Human-readable preview of a proposed tool action (sent before execution)."""

    tool_name: str
    title: str
    summary: str
    affected_resources: list[str]  # e.g. ["path/to/file.md", "https://..."]
    arguments: dict[str, Any]  # args that would be passed to the tool
    dry_run_result: str | None = None  # if the tool can compute a safe preview


@dataclass
class ToolResult:
    """Result of executing a tool."""

    success: bool
    content: str
    data: dict[str, Any] | None = None  # structured result for the model


@dataclass
class ToolContext:
    """Context passed to Tool.call (user_id, chat_id, embedding store, etc.)."""

    user_id: str
    chat_id: str | None
    # Optional: embedder, memory_store, etc. can be injected by the runner


class Tool(Protocol):
    """A single tool: name, description, schema, capabilities, and execution."""

    @property
    def name(self) -> str:
        ...

    @property
    def description(self) -> str:
        ...

    def args_schema(self) -> dict[str, Any]:
        """JSON Schema for the tool's arguments."""
        ...

    def capabilities(self) -> list[Capability]:
        """Which permission capabilities this tool requires."""
        ...

    async def preview(self, args: dict[str, Any], context: ToolContext) -> ToolPreview:
        """Produce a preview of the proposed action (before asking permission)."""
        ...

    async def call(self, args: dict[str, Any], context: ToolContext) -> ToolResult:
        """Execute the tool. Called only after permission is granted."""
        ...
