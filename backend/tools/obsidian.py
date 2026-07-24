"""Obsidian vault tool: read, search, backlinks, list by tag, write, delete (files), create_folder, delete_folder. Any file type."""

from __future__ import annotations

import re
import shutil
from enum import StrEnum
from pathlib import Path
from typing import Any

from backend.config import ObsidianRagConfig
from backend.interfaces.tools import Capability, ToolContext, ToolPreview, ToolResult, Tool
from backend.rag.obsidian_index import ObsidianIndexConfig, ObsidianVaultIndexer


class ObsidianAction(StrEnum):
    READ = "read"
    SEARCH = "search"
    BACKLINKS = "backlinks"
    LIST_BY_TAG = "list_by_tag"
    WRITE = "write"
    DELETE = "delete"
    CREATE_FOLDER = "create_folder"
    DELETE_FOLDER = "delete_folder"


class SearchMode(StrEnum):
    KEYWORD = "keyword"
    SEMANTIC = "semantic"
    HYBRID = "hybrid"


_RRF_K = 60


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


def _display_note_path(path: str) -> str:
    """Normalize stored/relative paths to note path without .md (tool read convention)."""
    p = (path or "").replace("\\", "/").strip()
    if p.lower().endswith(".md"):
        p = p[:-3]
    return p


def _rrf_fuse(result_lists: list[list[dict[str, Any]]], *, limit: int) -> list[dict[str, Any]]:
    """Reciprocal rank fusion over path-keyed hit lists."""
    scores: dict[str, float] = {}
    best: dict[str, dict[str, Any]] = {}
    for results in result_lists:
        for rank, item in enumerate(results):
            path = item["path"]
            scores[path] = scores.get(path, 0.0) + 1.0 / (_RRF_K + rank + 1)
            prev = best.get(path)
            if prev is None or len(str(item.get("snippet") or "")) > len(str(prev.get("snippet") or "")):
                best[path] = dict(item)
    ordered = sorted(scores.keys(), key=lambda p: -scores[p])[:limit]
    fused: list[dict[str, Any]] = []
    for path in ordered:
        row = dict(best[path])
        row["path"] = path
        row["score"] = scores[path]
        row["source"] = "hybrid"
        fused.append(row)
    return fused


class ObsidianTool(Tool):
    """
    Tool to interact with an Obsidian vault: read notes, keyword/semantic/hybrid search,
    backlinks, list by tag, write. Vault path is set at creation (e.g. from config).
    Uses OBSIDIAN_READ for read/search/backlinks/list_by_tag, OBSIDIAN_MODIFY for write.
    """

    def __init__(
            self,
            vault_path: str = "",
            *,
            rag_config: ObsidianRagConfig | None = None,
            embeddings_dir: str | Path | None = None,
    ) -> None:
        self._vault_path = (vault_path or "").strip()
        self._rag = rag_config or ObsidianRagConfig()
        self._embeddings_dir = Path(embeddings_dir).resolve() if embeddings_dir else None
        self._indexer: ObsidianVaultIndexer | None = None
        self._indexer_store_id: int | None = None

    @property
    def name(self) -> str:
        return "obsidian"

    @property
    def description(self) -> str:
        return (
            "Interact with the user's Obsidian vault: notes, canvases, and any file type. "
            "Actions: read (get file content; path with or without extension, default .md), "
            "search (keyword, semantic, or hybrid over .md; empty query = list all .md files), "
            "backlinks (notes linking to a note), list_by_tag (notes with a tag), write (create or overwrite any file), "
            "delete (remove a file), create_folder (create a folder), delete_folder (remove a folder and its contents). "
            "Prefer search mode=hybrid or semantic for meaning-based discovery, then read full notes by path."
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
                    "description": "Search query. For action=search. Omit or leave empty to list all .md files (keyword mode only).",
                },
                "mode": {
                    "type": "string",
                    "enum": [m.value for m in SearchMode],
                    "description": "Search mode for action=search: hybrid (default; keyword+semantic), semantic, or keyword.",
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
                    "description": "Max results for search. Default 20 for keyword; config search_top_k for semantic/hybrid.",
                },
            },
            "required": ["action"],
        }

    def capabilities(self, args: dict[str, Any]) -> list[Capability]:
        """Capabilities for this call: OBSIDIAN_READ for read-only actions, OBSIDIAN_MODIFY for write/delete."""
        action_str = (args.get("action") or ObsidianAction.READ.value).strip().lower()
        try:
            action = ObsidianAction(action_str)
        except ValueError:
            return []
        read_only = {
            ObsidianAction.READ,
            ObsidianAction.SEARCH,
            ObsidianAction.BACKLINKS,
            ObsidianAction.LIST_BY_TAG,
        }
        if action in read_only:
            return [Capability.OBSIDIAN_READ]
        return [Capability.OBSIDIAN_MODIFY]

    async def preview(self, args: dict[str, Any], context: ToolContext) -> ToolPreview:
        action = args.get("action", ObsidianAction.READ.value)
        path = args.get("path", "")
        summary = f"Obsidian: {action}"
        if path:
            summary += f" path={path!r}"
        if action == ObsidianAction.SEARCH.value:
            summary += f" query={args.get('query', '')!r} mode={args.get('mode', SearchMode.HYBRID.value)!r}"
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
            return await self._search(vault, args, context)
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

    def _resolve_search_mode(self, args: dict[str, Any]) -> SearchMode | ToolResult:
        raw = (args.get("mode") or SearchMode.HYBRID.value).strip().lower()
        try:
            return SearchMode(raw)
        except ValueError:
            return ToolResult(
                success=False,
                content=f"Unknown search mode: {raw!r}. Use keyword, semantic, or hybrid.",
            )

    def _get_indexer(self, context: ToolContext) -> ObsidianVaultIndexer | None:
        store = context.embedding_store
        embedder = context.embedder
        if store is None or embedder is None:
            return None
        store_id = id(store)
        if self._indexer is None or self._indexer_store_id != store_id:
            self._indexer = ObsidianVaultIndexer(
                self._vault_path,
                store,
                embedder,
                config=ObsidianIndexConfig.from_rag_config(self._rag),
                embeddings_dir=self._embeddings_dir,
            )
            self._indexer_store_id = store_id
        return self._indexer

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

    async def _search(self, vault: Path, args: dict[str, Any], context: ToolContext) -> ToolResult:
        mode_or_err = self._resolve_search_mode(args)
        if isinstance(mode_or_err, ToolResult):
            return mode_or_err
        mode = mode_or_err
        query = (args.get("query") or "").strip()

        if mode == SearchMode.KEYWORD:
            default_limit = 20
        else:
            default_limit = max(1, self._rag.search_top_k)
        if args.get("limit") is None:
            limit = default_limit
        else:
            limit = max(1, min(100, int(args.get("limit", default_limit))))

        # Empty query: list notes (keyword scan only; no embed/index).
        if not query:
            return await self._search_keyword(vault, query, limit)

        if mode == SearchMode.KEYWORD:
            return await self._search_keyword(vault, query, limit)

        indexer = self._get_indexer(context)
        if indexer is None:
            # Graceful degrade: hybrid/semantic without embed stack → keyword.
            return await self._search_keyword(vault, query, limit)

        max_files = self._rag.ensure_index_max_files
        await indexer.ensure_index(max_files=max_files if max_files > 0 else None)

        if mode == SearchMode.SEMANTIC:
            matches = await self._search_semantic(context, indexer.namespace, query, limit)
            return self._format_search_result(matches, query, mode)

        # hybrid
        keyword_matches = (await self._search_keyword(vault, query, limit)).data.get("matches") or []
        semantic_matches = await self._search_semantic(context, indexer.namespace, query, limit)
        fused = _rrf_fuse([keyword_matches, semantic_matches], limit=limit)
        return self._format_search_result(fused, query, mode)

    def _format_search_result(
            self,
            matches: list[dict[str, Any]],
            query: str,
            mode: SearchMode,
    ) -> ToolResult:
        lines: list[str] = []
        for m in matches:
            path = m.get("path", "")
            snippet = (m.get("snippet") or "").strip()
            heading = (m.get("heading") or "").strip()
            score = m.get("score")
            parts = [f"- {path}"]
            if heading:
                parts.append(f"[{heading}]")
            if score is not None:
                try:
                    parts.append(f"(score={float(score):.3f})")
                except (TypeError, ValueError):
                    pass
            line = " ".join(parts)
            if snippet:
                line += f": {snippet}"
            lines.append(line)
        label = mode.value
        content = (
            f"Found {len(matches)} note(s) ({label}):\n" + "\n".join(lines)
            if lines
            else f"No matches ({label})."
        )
        return ToolResult(
            success=True,
            content=content,
            data={"matches": matches, "query": query, "mode": mode.value},
        )

    async def _search_semantic(
            self,
            context: ToolContext,
            namespace: str,
            query: str,
            limit: int,
    ) -> list[dict[str, Any]]:
        vectors = await context.embedder([query])
        if not vectors:
            return []
        hits = await context.embedding_store.search(namespace, vectors[0], k=max(limit * 3, limit))
        matches: list[dict[str, Any]] = []
        seen: set[str] = set()
        for chunk_id, score, meta in hits:
            path = _display_note_path(str(meta.get("path") or chunk_id.split("#", 1)[0]))
            if path in seen:
                continue
            seen.add(path)
            snippet = str(meta.get("snippet") or "").strip()
            heading = str(meta.get("heading") or "").strip()
            matches.append({
                "path": path,
                "snippet": snippet,
                "heading": heading,
                "score": float(score),
                "source": "semantic",
                "chunk_id": chunk_id,
            })
            if len(matches) >= limit:
                break
        return matches

    async def _search_keyword(self, vault: Path, query: str, limit: int) -> ToolResult:
        seen: set[str] = set()
        matches: list[dict[str, Any]] = []

        def add(path: Path, snippet: str) -> None:
            name = _note_name_from_path(vault, path)
            if name in seen or len(matches) >= limit:
                return
            seen.add(name)
            matches.append({"path": name, "snippet": snippet, "source": "keyword"})

        if not query:
            # Empty query: global search — return all .md files (up to limit)
            for path in _list_md_files(vault):
                if len(matches) >= limit:
                    break
                try:
                    text = path.read_text(encoding="utf-8", errors="replace")
                    first_line = (text.split("\n")[0] or "").strip()[:80]
                    snippet = first_line or "(no content)"
                except Exception:
                    snippet = "(file)"
                add(path, snippet)
            lines = [f"- {m['path']}" for m in matches]
            content = f"Found {len(matches)} note(s) (all .md files, limit {limit}):\n" + "\n".join(lines) if lines else "No notes in vault."
            return ToolResult(
                success=True,
                content=content,
                data={"matches": matches, "query": "", "mode": SearchMode.KEYWORD.value},
            )

        query_lower = query.lower()

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
            data={"matches": matches, "query": query, "mode": SearchMode.KEYWORD.value},
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
