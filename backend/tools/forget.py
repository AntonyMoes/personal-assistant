"""Forget tool: delete a memory the user asked to forget or that is no longer relevant."""

from __future__ import annotations

from typing import Any

from backend.interfaces.tools import Capability, ToolContext, ToolPreview, ToolResult, Tool


class ForgetTool(Tool):
    """
    Tool the model can call when the user asks to forget something or when a memory
    is no longer accurate/relevant. Deletes by key (one memory per key per user).
    """
    NAME = "forget"

    @property
    def name(self) -> str:
        return self.NAME

    @property
    def description(self) -> str:
        return (
            "Permanently remove a memory. Use only when the user explicitly asks to forget, remove, or delete "
            "a memory (e.g. 'forget that', 'remove that memory', 'delete that'). "
            "Do not use forget when the user asks to update or change a memory—use remember with the same key and new content instead."
        )

    def args_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "key": {
                    "type": "string",
                    "description": "The key of the memory to delete (e.g. 'favorite_color', 'birthday').",
                },
            },
            "required": ["key"],
        }

    def capabilities(self) -> list[Capability]:
        return [Capability.MEMORY_WRITE]

    async def preview(self, args: dict[str, Any], context: ToolContext) -> ToolPreview:
        key = args.get("key", "")
        return ToolPreview(
            tool_name=self.name,
            title="Delete memory",
            summary=f"Will forget memory with key: {key!r}",
            affected_resources=[],
            arguments=args,
            dry_run_result=None,
        )

    async def call(self, args: dict[str, Any], context: ToolContext) -> ToolResult:
        if not context.memory_store:
            return ToolResult(success=False, content="Memory store not available.")
        key = (args.get("key") or "").strip()
        if not key:
            return ToolResult(success=False, content="key is required.")
        try:
            existing = await context.memory_store.get_memory_by_key(context.user_id, key)
            if not existing:
                return ToolResult(
                    success=False,
                    content=f"No memory found with key {key!r}.",
                )
            content_snapshot = existing.content
            memory_id = existing.id
            ok = await context.memory_store.delete_memory(existing.id)
            if not ok:
                return ToolResult(success=False, content="Failed to delete memory.")
            return ToolResult(
                success=True,
                content=f"Deleted memory {memory_id}.",
                data={"id": memory_id, "key": existing.key, "content": content_snapshot},
            )
        except Exception as e:
            return ToolResult(success=False, content=str(e))
