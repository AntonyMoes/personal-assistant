"""Obsidian vault tool: read, search, backlinks, list by tag, write, delete (files), create_folder, delete_folder. Any file type."""

from __future__ import annotations

import re
import shutil
from enum import StrEnum
from pathlib import Path
from typing import Any

from backend.interfaces.tools import Capability, ToolContext, ToolPreview, ToolResult, Tool


class ObsidianAction(StrEnum):
    READ = "read"
    SEARCH = "search"
    BACKLINKS = "backlinks"
    LIST_BY_TAG = "list_by_tag"
    WRITE = "write"
    DELETE = "delete"
    CREATE_FOLDER = "create_folder"
    DELETE_FOLDER = "delete_folder"


def _vault_root_from_path(vault_path: str) -> Path | None:
    path = (vault_path or "").strip()
    if not path:
        return None
    p = Path(path).resolve()
    return p if p.is_dir() else None


def _normalize_ref(ref: str) -> list[str] | None:
    """Normalize path ref to parts under vault; None if invalid (.. or .)."""
    ref = (ref or "").strip().replace("\\", "/")
    if not ref:
        return None
    parts = [p for p in ref.split("/") if p and p != "."]
    if any(p == ".." for p in parts):
        return None
    return parts


def _resolve_file_path(vault: Path, path_ref: str, should_exist: bool = True) -> Path | None:
    """Resolve a file path under vault. If path has no extension, default to .md (notes). Any extension allowed."""
    parts = _normalize_ref(path_ref)
    if not parts:
        return None
    # If last segment has no extension, treat as note and add .md
    if not Path(parts[-1]).suffix:
        parts[-1] = f"{parts[-1]}.md"
    full = (vault / Path(*parts)).resolve()
    try:
        full.relative_to(vault.resolve())
    except ValueError:
        return None
    return full if not should_exist or full.is_file() else None


def _resolve_folder_path(vault: Path, path_ref: str, should_exist: bool | None = None) -> Path | None:
    """Resolve a folder path under vault. should_exist: True = must exist, False = must not exist, None = don't check."""
    parts = _normalize_ref(path_ref)
    if not parts:
        return None
    full = (vault / Path(*parts)).resolve()
    try:
        full.relative_to(vault.resolve())
    except ValueError:
        return None
    if should_exist is True and not full.is_dir():
        return None
    if should_exist is False and full.exists():
        return None
    return full


def _list_md_files(vault: Path) -> list[Path]:
    return list(vault.rglob("*.md"))


def _extract_wikilinks(content: str) -> list[str]:
    """Extract [[link]] or [[link|label]] targets (note names) from content."""
    # [[note name]] or [[note name|label]]
    pattern = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]*)?\]\]")
    return list(pattern.findall(content))


def _extract_tags(content: str) -> set[str]:
    """Extract #tag from content (word characters, may have / or -)."""
    pattern = re.compile(r"#([a-zA-Z_][a-zA-Z0-9_/-]*)")
    return set(pattern.findall(content))


def _rel_path(vault: Path, path: Path) -> str:
    """Relative path under vault for display (forward slashes, with extension)."""
    try:
        return str(path.relative_to(vault)).replace("\\", "/")
    except ValueError:
        return path.name


def _note_name_from_path(vault: Path, path: Path) -> str:
    """Relative path without .md for display (backward compat for note-only contexts)."""
    try:
        rel = path.relative_to(vault)
        name = str(rel.with_suffix("")).replace("\\", "/")
        return name
    except ValueError:
        return path.name


class ObsidianTool(Tool):
    """
    Tool to interact with an Obsidian vault: read notes, keyword search, backlinks, list by tag, write.
    Vault path is set at creation (e.g. from config). Uses OBSIDIAN_READ for read/search/backlinks/list_by_tag,
    OBSIDIAN_MODIFY for write.
    """

    def __init__(self, vault_path: str = "") -> None:
        self._vault_path = (vault_path or "").strip()

    @property
    def name(self) -> str:
        return "obsidian"

    @property
    def description(self) -> str:
        return (
            "Interact with the user's Obsidian vault: notes, canvases, and any file type. "
            "Actions: read (get file content; path with or without extension, default .md), search (keyword in .md), "
            "backlinks (notes linking to a note), list_by_tag (notes with a tag), write (create or overwrite any file), "
            "delete (remove a file), create_folder (create a folder), delete_folder (remove a folder and its contents)."
        )

    def args_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": [a.value for a in ObsidianAction],
                    "description": "Action to perform.",
                },
                "path": {
                    "type": "string",
                    "description": "File path with optional extension (e.g. 'My Note' or 'folder/note.md', 'folder/Board.canvas'). Default .md if omitted. For create_folder/delete_folder, folder path (no file extension).",
                },
                "query": {
                    "type": "string",
                    "description": "Search query (keyword). For action=search.",
                },
                "tag": {
                    "type": "string",
                    "description": "Tag without # (e.g. 'work'). For action=list_by_tag.",
                },
                "content": {
                    "type": "string",
                    "description": "File content (e.g. markdown or JSON for .canvas). For action=write.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max results for search. Default 20.",
                },
            },
            "required": ["action"],
        }

    def capabilities(self) -> list[Capability]:
        return [Capability.OBSIDIAN_READ, Capability.OBSIDIAN_MODIFY]

    async def preview(self, args: dict[str, Any], context: ToolContext) -> ToolPreview:
        action = args.get("action", ObsidianAction.READ.value)
        path = args.get("path", "")
        summary = f"Obsidian: {action}"
        if path:
            summary += f" path={path!r}"
        if action == ObsidianAction.SEARCH.value:
            summary += f" query={args.get('query', '')!r}"
        if action == ObsidianAction.LIST_BY_TAG.value:
            summary += f" tag=#{args.get('tag', '')}"
        if action == ObsidianAction.WRITE.value:
            summary += " (create/overwrite file)"
        if action == ObsidianAction.DELETE.value:
            summary += " (remove file)"
        if action == ObsidianAction.CREATE_FOLDER.value:
            summary += " (create folder)"
        if action == ObsidianAction.DELETE_FOLDER.value:
            summary += " (remove folder)"
        return ToolPreview(
            tool_name=self.name,
            title=f"Obsidian {action}",
            summary=summary,
            affected_resources=[path] if path else [],
            arguments=args,
            dry_run_result=None,
        )

    async def call(self, args: dict[str, Any], context: ToolContext) -> ToolResult:
        vault = _vault_root_from_path(self._vault_path)
        if not vault:
            return ToolResult(success=False, content="Obsidian vault not configured (missing or invalid vault path).")
        action_str = (args.get("action") or ObsidianAction.READ.value).strip().lower()
        try:
            action = ObsidianAction(action_str)
        except ValueError:
            return ToolResult(success=False, content=f"Unknown action: {action_str!r}")
        if action == ObsidianAction.READ:
            return await self._read(vault, args)
        if action == ObsidianAction.SEARCH:
            return await self._search(vault, args)
        if action == ObsidianAction.BACKLINKS:
            return await self._backlinks(vault, args)
        if action == ObsidianAction.LIST_BY_TAG:
            return await self._list_by_tag(vault, args)
        if action == ObsidianAction.WRITE:
            return await self._write(vault, args)
        if action == ObsidianAction.DELETE:
            return await self._delete(vault, args)
        if action == ObsidianAction.CREATE_FOLDER:
            return await self._create_folder(vault, args)
        if action == ObsidianAction.DELETE_FOLDER:
            return await self._delete_folder(vault, args)
        return ToolResult(success=False, content=f"Unknown action: {action!r}")

    async def _read(self, vault: Path, args: dict[str, Any]) -> ToolResult:
        path_arg = args.get("path") or ""
        file_path = _resolve_file_path(vault, path_arg, should_exist=True)
        if not file_path:
            return ToolResult(success=False, content="Missing or invalid 'path' for read, or file does not exist.")
        try:
            text = file_path.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            return ToolResult(success=False, content=f"Failed to read file: {e}")
        return ToolResult(
            success=True,
            content=text,
            data={"path": _rel_path(vault, file_path), "content": text},
        )

    async def _search(self, vault: Path, args: dict[str, Any]) -> ToolResult:
        query = (args.get("query") or "").strip()
        if not query:
            return ToolResult(success=False, content="Missing 'query' for search.")
        limit = max(1, min(100, int(args.get("limit", 20))))
        query_lower = query.lower()
        seen: set[str] = set()
        matches: list[dict[str, Any]] = []

        def add(path: Path, snippet: str) -> None:
            name = _note_name_from_path(vault, path)
            if name in seen or len(matches) >= limit:
                return
            seen.add(name)
            matches.append({"path": name, "snippet": snippet})

        # 1) Match by content (keyword in body)
        for path in _list_md_files(vault):
            if len(matches) >= limit:
                break
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            if query_lower in text.lower():
                idx = text.lower().find(query_lower)
                start = max(0, idx - 40)
                end = min(len(text), idx + len(query) + 40)
                snippet = (text[start:end] or "").replace("\n", " ")
                add(path, snippet)

        # 2) Match by note name/path (not exact: query in path or stem)
        for path in _list_md_files(vault):
            if len(matches) >= limit:
                break
            name = _note_name_from_path(vault, path)
            if name in seen:
                continue
            if query_lower in name.lower() or query_lower in path.stem.lower():
                try:
                    text = path.read_text(encoding="utf-8", errors="replace")
                    snippet = (text[:80] or "").replace("\n", " ")
                except Exception:
                    snippet = "(matched by name)"
                add(path, snippet)

        lines = [f"- {m['path']}" for m in matches]
        content = f"Found {len(matches)} note(s):\n" + "\n".join(lines) if lines else "No matches."
        return ToolResult(
            success=True,
            content=content,
            data={"matches": matches, "query": query},
        )

    async def _backlinks(self, vault: Path, args: dict[str, Any]) -> ToolResult:
        path_arg = args.get("path") or ""
        target_path = _resolve_file_path(vault, path_arg, should_exist=True)
        if not target_path:
            return ToolResult(success=False, content="Missing or invalid 'path' for backlinks.")
        target_name = _note_name_from_path(vault, target_path)
        target_resolved = target_path.resolve()
        backlinks: list[str] = []
        for path in _list_md_files(vault):
            if path == target_path:
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            for link in _extract_wikilinks(text):
                if not link.strip():
                    continue
                # Resolve [[link]] relative to the linking file's directory
                ref = link.strip()
                if not ref.endswith(".md"):
                    ref = ref + ".md"
                link_path = (path.parent / ref).resolve()
                try:
                    link_path.relative_to(vault)
                except ValueError:
                    continue
                if link_path == target_resolved:
                    backlinks.append(_note_name_from_path(vault, path))
                    break
        # Include backlink paths in content so the model sees them
        content = f"Found {len(backlinks)} backlink(s) to {target_name}:\n" + "\n".join(f"- {p}" for p in backlinks) if backlinks else f"No backlinks to {target_name}."
        return ToolResult(
            success=True,
            content=content,
            data={"target": target_name, "backlinks": backlinks},
        )

    async def _list_by_tag(self, vault: Path, args: dict[str, Any]) -> ToolResult:
        tag_arg = (args.get("tag") or "").strip()
        if not tag_arg:
            return ToolResult(success=False, content="Missing 'tag' for list_by_tag.")
        tag = tag_arg if tag_arg.startswith("#") else f"#{tag_arg}"
        found: list[str] = []
        for path in _list_md_files(vault):
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            if tag in text or tag_arg in _extract_tags(text):
                found.append(_note_name_from_path(vault, path))
        # Include paths in content so the model sees them
        content = f"Found {len(found)} note(s) with tag {tag}:\n" + "\n".join(f"- {p}" for p in found) if found else f"No notes with tag {tag}."
        return ToolResult(
            success=True,
            content=content,
            data={"tag": tag, "paths": found},
        )

    async def _write(self, vault: Path, args: dict[str, Any]) -> ToolResult:
        path_arg = args.get("path") or ""
        file_path = _resolve_file_path(vault, path_arg, should_exist=False)
        if not file_path:
            return ToolResult(success=False, content="Missing or invalid 'path' for write.")
        content = args.get("content")
        if content is None:
            content = ""
        content = str(content)
        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")
        except Exception as e:
            return ToolResult(success=False, content=f"Failed to write file: {e}")
        return ToolResult(
            success=True,
            content=f"Wrote file: {_rel_path(vault, file_path)}",
            data={"path": _rel_path(vault, file_path)},
        )

    async def _delete(self, vault: Path, args: dict[str, Any]) -> ToolResult:
        path_arg = args.get("path") or ""
        file_path = _resolve_file_path(vault, path_arg, should_exist=True)
        if not file_path:
            return ToolResult(success=False, content="Missing or invalid 'path' for delete, or file does not exist.")
        try:
            file_path.unlink()
        except Exception as e:
            return ToolResult(success=False, content=f"Failed to delete file: {e}")
        name = _rel_path(vault, file_path)
        return ToolResult(
            success=True,
            content=f"Deleted file: {name}",
            data={"path": name},
        )

    async def _create_folder(self, vault: Path, args: dict[str, Any]) -> ToolResult:
        path_arg = (args.get("path") or "").strip()
        if not path_arg:
            return ToolResult(success=False, content="Missing 'path' for create_folder.")
        folder_path = _resolve_folder_path(vault, path_arg, should_exist=None)
        if not folder_path:
            return ToolResult(success=False, content="Invalid 'path' for create_folder.")
        try:
            folder_path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            return ToolResult(success=False, content=f"Failed to create folder: {e}")
        name = _rel_path(vault, folder_path)
        return ToolResult(
            success=True,
            content=f"Created folder: {name}",
            data={"path": name},
        )

    async def _delete_folder(self, vault: Path, args: dict[str, Any]) -> ToolResult:
        path_arg = (args.get("path") or "").strip()
        if not path_arg:
            return ToolResult(success=False, content="Missing 'path' for delete_folder.")
        folder_path = _resolve_folder_path(vault, path_arg, should_exist=True)
        if not folder_path:
            return ToolResult(success=False, content="Missing or invalid 'path' for delete_folder, or folder does not exist.")
        try:
            shutil.rmtree(folder_path)
        except Exception as e:
            return ToolResult(success=False, content=f"Failed to delete folder: {e}")
        name = _rel_path(vault, folder_path)
        return ToolResult(
            success=True,
            content=f"Deleted folder: {name}",
            data={"path": name},
        )
