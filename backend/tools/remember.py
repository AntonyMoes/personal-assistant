"""Remember tool: save a fact or preference the user asked the model to remember."""

from __future__ import annotations

from typing import Any

from backend.interfaces.tools import Capability, ToolContext, ToolPreview, ToolResult


class RememberTool:
    """
    Tool the model can call when the user says to remember something, or when it learns
    a preference/fact worth storing. Uses the same preview-and-execute flow as other tools;
    permission for MEMORY_WRITE can be set to "allow" by default so it feels implicit.
    """

    @property
    def name(self) -> str:
        return "remember"

    @property
    def description(self) -> str:
        return (
            "Save something the user asked you to remember, or a preference/fact they shared. "
            "Use when the user says 'remember that ...', 'don't forget ...', or when you learn "
            "something about them (name, preferences, context) they would want stored for future chats."
        )

    def args_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "key": {
                    "type": "string",
                    "description": "Short label for the memory (e.g. 'favorite_color', 'birthday', 'prefers_dark_mode').",
                },
                "content": {
                    "type": "string",
                    "description": "The fact or content to remember.",
                },
                "chat_id": {
                    "type": "string",
                    "description": "Optional. If set, the memory is scoped to this chat; if omitted, it is global.",
                },
            },
            "required": ["key", "content"],
        }

    def capabilities(self) -> list[Capability]:
        return [Capability.MEMORY_WRITE]

    async def preview(self, args: dict[str, Any], context: ToolContext) -> ToolPreview:
        key = args.get("key", "")
        content = args.get("content", "")[:200]
        chat_id = args.get("chat_id")
        scope = f"chat {chat_id}" if chat_id else "global"
        return ToolPreview(
            tool_name=self.name,
            title="Save memory",
            summary=f"Will remember: [{key}] = {content!r} (scope: {scope})",
            affected_resources=[],
            arguments=args,
            dry_run_result=None,
        )

    async def call(self, args: dict[str, Any], context: ToolContext) -> ToolResult:
        if not context.memory_store:
            return ToolResult(success=False, content="Memory store not available.")
        key = (args.get("key") or "").strip()
        content = (args.get("content") or "").strip()
        if not key or not content:
            return ToolResult(success=False, content="key and content are required.")
        chat_id = args.get("chat_id")
        if isinstance(chat_id, str) and not chat_id.strip():
            chat_id = None
        try:
            record = await context.memory_store.create_memory(
                context.user_id,
                key=key,
                content=content,
                chat_id=chat_id or context.chat_id,
            )
            return ToolResult(
                success=True,
                content=f"Saved memory with id {record.id}.",
                data={"id": record.id, "key": record.key},
            )
        except Exception as e:
            return ToolResult(success=False, content=str(e))
