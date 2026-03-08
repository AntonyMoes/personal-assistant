#!/usr/bin/env python3
"""
Interactive tool testing: load config and all tools, then call them from the shell.

From an existing interactive shell (run from repo root or add it to path):

  import sys
  sys.path.insert(0, "/path/to/personal-assistant")   # repo root
  from scripts.tool_runner import call, preview, list_tools, reload_config

  call("obsidian", {"action": "search", "query": "Inbox"})
  call("obsidian", {"action": "read", "path": "Projects/Inbox"})
  call("remember", {"key": "test", "content": "hello"})
  call("forget", {"key": "test"})
  list_tools()

Or run the script to start a new shell with tools preloaded:

  python scripts/tool_runner.py
  python -i scripts/tool_runner.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

# Ensure repo root is on path when run as script
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from backend.config import load_config
from backend.interfaces.tools import ToolContext
from backend.storage import (
    create_chat_store,
    create_embedding_store,
    create_memory_store,
)
from backend.tools import ForgetTool, ObsidianTool, RememberTool


def _load(config_path: str | Path | None = None):
    """Load config from file. Uses CONFIG_PATH env or config.example.yaml if present."""
    path = config_path
    if path is None:
        path = os.environ.get("CONFIG_PATH")
    if path is None:
        for name in ("config.yaml", "config.example.yaml"):
            p = _REPO_ROOT / name
            if p.is_file():
                path = p
                break
    return load_config(path)


def _make_tools_and_context(config_path: str | Path | None = None):
    """Build config, stores, tools, and context. Returns (config, tools_by_name, context)."""
    config = _load(config_path)
    memory_store = create_memory_store(config.storage)
    vault_path = getattr(config.app, "obsidian_vault_path", "") or ""
    tools_list = [
        RememberTool(),
        ForgetTool(),
        ObsidianTool(vault_path=vault_path),
    ]
    tools_by_name = {t.name: t for t in tools_list}
    user_id = config.app.default_user_id
    context = ToolContext(
        user_id=user_id,
        chat_id=None,
        memory_store=memory_store,
        embedding_store=create_embedding_store(config.storage),
        embedder=None,
    )
    return config, tools_by_name, context


# Load once at import
config, tools_by_name, context = _make_tools_and_context()


def call(name: str, args: dict) -> object:
    """
    Call a tool by name with the given args. Returns the ToolResult (has .success, .content, .data).

    Example:
      r = call("obsidian", {"action": "search", "query": "- [ ]"})
      print(r.success, r.content)
      r = call("obsidian", {"action": "read", "path": "Projects/Inbox"})
    """
    tool = tools_by_name.get(name)
    if not tool:
        raise KeyError(f"Unknown tool: {name}. Available: {list(tools_by_name.keys())}")
    return asyncio.run(tool.call(args, context))


def preview(name: str, args: dict) -> object:
    """Run the tool's preview (no side effects). Returns ToolPreview."""
    tool = tools_by_name.get(name)
    if not tool:
        raise KeyError(f"Unknown tool: {name}. Available: {list(tools_by_name.keys())}")
    return asyncio.run(tool.preview(args, context))


def list_tools() -> None:
    """Print each tool name, description, and required args."""
    for name, tool in tools_by_name.items():
        schema = tool.args_schema()
        req = schema.get("required", [])
        desc = tool.description
        print(f"  {name}: {desc[:70] + '...' if len(desc) > 70 else desc}")
        print(f"    required: {req}")
        print()


def reload_config(config_path: str | Path | None = None) -> None:
    """Reload config and rebuild tools and context (e.g. after changing config file)."""
    global config, tools_by_name, context
    config, tools_by_name, context = _make_tools_and_context(config_path)
    print("Config and tools reloaded.")


if __name__ == "__main__":
    print("Tools loaded from config. Usage:")
    print("  call(name, args)     - run tool, returns ToolResult (.success, .content, .data)")
    print("  preview(name, args)  - tool preview only")
    print("  list_tools()         - show tool names and args")
    print("  reload_config(path)  - reload config and tools")
    print()
    print("Examples:")
    print('  call("obsidian", {"action": "search", "query": "Inbox"})')
    print('  call("obsidian", {"action": "read", "path": "Projects/Inbox"})')
    print('  call("remember", {"key": "x", "content": "y"})')
    print()
    import code
    code.interact(local={"call": call, "preview": preview, "list_tools": list_tools, "reload_config": reload_config, "config": config, "tools_by_name": tools_by_name, "context": context})
