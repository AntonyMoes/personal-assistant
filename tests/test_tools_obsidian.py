"""Tests for ObsidianTool. Use tmp_path as vault; no real vault is touched."""

import pytest

from backend.interfaces.tools import Capability, ToolContext
from backend.tools.obsidian import ObsidianTool


@pytest.fixture
def no_vault_ctx():
    """Context for tool calls (vault is on the tool instance, not context)."""
    return ToolContext(user_id="u1", chat_id="c1", memory_store=None)


@pytest.fixture
def tool():
    """Tool with no vault (for tests that expect not configured)."""
    return ObsidianTool(vault_path="")


@pytest.fixture
def tool_with_vault(tmp_path):
    """Tool with vault_path set to a temp directory."""
    return ObsidianTool(vault_path=str(tmp_path))


def test_obsidian_tool_name_and_capabilities(tool_with_vault):
    assert tool_with_vault.name == "obsidian"
    read_caps = tool_with_vault.capabilities({"action": "read"})
    write_caps = tool_with_vault.capabilities({"action": "write"})
    assert Capability.OBSIDIAN_READ in read_caps
    assert Capability.OBSIDIAN_MODIFY not in read_caps
    assert Capability.OBSIDIAN_MODIFY in write_caps
    assert Capability.OBSIDIAN_READ not in write_caps


def test_obsidian_tool_args_schema(tool_with_vault):
    schema = tool_with_vault.args_schema()
    assert schema["type"] == "object"
    assert "action" in schema["properties"]
    assert set(schema["properties"]["action"]["enum"]) == {
        "read", "search", "backlinks", "list_by_tag", "write", "delete",
        "create_folder", "delete_folder",
    }
    assert set(schema["properties"]["mode"]["enum"]) == {"keyword", "semantic", "hybrid"}
    assert "action" in schema["required"]


@pytest.mark.asyncio
async def test_obsidian_tool_call_no_vault_configured(tool, no_vault_ctx):
    """Tool created with empty vault_path returns not configured."""
    result = await tool.call({"action": "read", "path": "Any"}, no_vault_ctx)
    assert result.success is False
    assert "not configured" in result.content.lower()


@pytest.mark.asyncio
async def test_obsidian_read(tool_with_vault, no_vault_ctx, tmp_path):
    (tmp_path / "Note.md").write_text("Hello from note.", encoding="utf-8")
    result = await tool_with_vault.call({"action": "read", "path": "Note"}, no_vault_ctx)
    assert result.success is True
    assert "Hello from note" in result.content
    assert result.data and result.data.get("path") == "Note.md"


@pytest.mark.asyncio
async def test_obsidian_read_with_path(tool_with_vault, no_vault_ctx, tmp_path):
    (tmp_path / "sub").mkdir(exist_ok=True)
    (tmp_path / "sub" / "Deep.md").write_text("Deep content.", encoding="utf-8")
    result = await tool_with_vault.call({"action": "read", "path": "sub/Deep"}, no_vault_ctx)
    assert result.success is True
    assert "Deep content" in result.content


@pytest.mark.asyncio
async def test_obsidian_read_exact_path_only(tool_with_vault, no_vault_ctx, tmp_path):
    """Read requires exact path; note in folder is not found by bare name."""
    (tmp_path / "Projects").mkdir(exist_ok=True)
    (tmp_path / "Projects" / "Inbox.md").write_text("Tasks in folder.", encoding="utf-8")
    result = await tool_with_vault.call({"action": "read", "path": "Inbox"}, no_vault_ctx)
    assert result.success is False
    result2 = await tool_with_vault.call({"action": "read", "path": "Projects/Inbox"}, no_vault_ctx)
    assert result2.success is True
    assert "Tasks in folder" in result2.content


@pytest.mark.asyncio
async def test_obsidian_search_matches_by_note_name(tool_with_vault, no_vault_ctx, tmp_path):
    """Search matches by note name/path (not exact), so notes in folders are findable."""
    (tmp_path / "Projects").mkdir(exist_ok=True)
    (tmp_path / "Projects" / "Inbox.md").write_text("Some content.", encoding="utf-8")
    result = await tool_with_vault.call({"action": "search", "query": "Inbox", "limit": 10}, no_vault_ctx)
    assert result.success is True
    assert result.data and "matches" in result.data
    paths = [m["path"] for m in result.data["matches"]]
    assert "Projects/Inbox" in paths
    assert "Projects/Inbox" in result.content


@pytest.mark.asyncio
async def test_obsidian_read_missing_note(tool_with_vault, no_vault_ctx):
    result = await tool_with_vault.call({"action": "read", "path": "Nonexistent"}, no_vault_ctx)
    assert result.success is False
    assert "path" in result.content.lower() and ("invalid" in result.content.lower() or "exist" in result.content.lower())


@pytest.mark.asyncio
async def test_obsidian_search(tool_with_vault, no_vault_ctx, tmp_path):
    (tmp_path / "A.md").write_text("apple banana", encoding="utf-8")
    (tmp_path / "B.md").write_text("banana cherry", encoding="utf-8")
    (tmp_path / "C.md").write_text("cherry only", encoding="utf-8")
    result = await tool_with_vault.call({"action": "search", "query": "banana", "limit": 10}, no_vault_ctx)
    assert result.success is True
    assert result.data and "matches" in result.data
    paths = {m["path"] for m in result.data["matches"]}
    assert "A" in paths and "B" in paths
    assert "C" not in paths
    # Paths must appear in content so the model can use them for read() on next turn
    assert "A" in result.content and "B" in result.content


@pytest.mark.asyncio
async def test_obsidian_search_empty_query_returns_all_files(tool_with_vault, no_vault_ctx, tmp_path):
    """Empty query is a global search that returns all .md files (up to limit)."""
    (tmp_path / "One.md").write_text("First note.", encoding="utf-8")
    (tmp_path / "Two.md").write_text("Second note.", encoding="utf-8")
    (tmp_path / "sub").mkdir(exist_ok=True)
    (tmp_path / "sub" / "Three.md").write_text("Third.", encoding="utf-8")
    result = await tool_with_vault.call({"action": "search", "query": "", "limit": 10}, no_vault_ctx)
    assert result.success is True
    assert result.data and "matches" in result.data
    paths = {m["path"] for m in result.data["matches"]}
    assert paths == {"One", "Two", "sub/Three"}
    assert "all .md files" in result.content or "Found 3 note" in result.content


@pytest.mark.asyncio
async def test_obsidian_backlinks(tool_with_vault, no_vault_ctx, tmp_path):
    (tmp_path / "Target.md").write_text("I am the target.", encoding="utf-8")
    (tmp_path / "Source.md").write_text("See [[Target]] for more.", encoding="utf-8")
    result = await tool_with_vault.call({"action": "backlinks", "path": "Target"}, no_vault_ctx)
    assert result.success is True
    assert result.data and "backlinks" in result.data
    assert "Source" in result.data["backlinks"]


@pytest.mark.asyncio
async def test_obsidian_list_by_tag(tool_with_vault, no_vault_ctx, tmp_path):
    (tmp_path / "WorkNote.md").write_text("Notes #work and #project", encoding="utf-8")
    (tmp_path / "Other.md").write_text("No tag here.", encoding="utf-8")
    result = await tool_with_vault.call({"action": "list_by_tag", "tag": "work"}, no_vault_ctx)
    assert result.success is True
    assert result.data and "paths" in result.data
    assert "WorkNote" in result.data["paths"]
    assert "Other" not in result.data["paths"]


@pytest.mark.asyncio
async def test_obsidian_write(tool_with_vault, no_vault_ctx, tmp_path):
    result = await tool_with_vault.call({"action": "write", "path": "NewNote", "content": "Written by test."}, no_vault_ctx)
    assert result.success is True
    assert (tmp_path / "NewNote.md").read_text(encoding="utf-8") == "Written by test."


@pytest.mark.asyncio
async def test_obsidian_write_then_read(tool_with_vault, no_vault_ctx, tmp_path):
    await tool_with_vault.call({"action": "write", "path": "Wrote", "content": "Content here."}, no_vault_ctx)
    result = await tool_with_vault.call({"action": "read", "path": "Wrote"}, no_vault_ctx)
    assert result.success is True
    assert result.content == "Content here."


@pytest.mark.asyncio
async def test_obsidian_delete(tool_with_vault, no_vault_ctx, tmp_path):
    (tmp_path / "ToDelete.md").write_text("Will be removed.", encoding="utf-8")
    assert (tmp_path / "ToDelete.md").is_file()
    result = await tool_with_vault.call({"action": "delete", "path": "ToDelete"}, no_vault_ctx)
    assert result.success is True
    assert "Deleted file" in result.content
    assert not (tmp_path / "ToDelete.md").exists()


@pytest.mark.asyncio
async def test_obsidian_delete_missing_note(tool_with_vault, no_vault_ctx):
    result = await tool_with_vault.call({"action": "delete", "path": "Nonexistent"}, no_vault_ctx)
    assert result.success is False
    assert "path" in result.content.lower() or "not found" in result.content.lower() or "does not exist" in result.content.lower()


@pytest.mark.asyncio
async def test_obsidian_read_write_delete_canvas(tool_with_vault, no_vault_ctx, tmp_path):
    """Read, write, delete work for any file type (e.g. .canvas)."""
    canvas_path = tmp_path / "Boards" / "Board.canvas"
    canvas_path.parent.mkdir(parents=True, exist_ok=True)
    canvas_path.write_text('{"nodes":[]}', encoding="utf-8")
    r = await tool_with_vault.call({"action": "read", "path": "Boards/Board.canvas"}, no_vault_ctx)
    assert r.success is True
    assert "nodes" in r.content
    assert r.data and r.data.get("path") == "Boards/Board.canvas"
    w = await tool_with_vault.call({"action": "write", "path": "Boards/Other.canvas", "content": '{"nodes":[{"id":"1"}]}'}, no_vault_ctx)
    assert w.success is True
    assert (tmp_path / "Boards" / "Other.canvas").read_text(encoding="utf-8") == '{"nodes":[{"id":"1"}]}'
    d = await tool_with_vault.call({"action": "delete", "path": "Boards/Board.canvas"}, no_vault_ctx)
    assert d.success is True
    assert not canvas_path.exists()


@pytest.mark.asyncio
async def test_obsidian_create_folder(tool_with_vault, no_vault_ctx, tmp_path):
    result = await tool_with_vault.call({"action": "create_folder", "path": "Projects/NewFolder"}, no_vault_ctx)
    assert result.success is True
    assert "Created folder" in result.content
    assert (tmp_path / "Projects" / "NewFolder").is_dir()
    # Idempotent: create again is ok (exist_ok=True)
    result2 = await tool_with_vault.call({"action": "create_folder", "path": "Projects/NewFolder"}, no_vault_ctx)
    assert result2.success is True


@pytest.mark.asyncio
async def test_obsidian_delete_folder(tool_with_vault, no_vault_ctx, tmp_path):
    (tmp_path / "ToRemove").mkdir(parents=True, exist_ok=True)
    (tmp_path / "ToRemove" / "file.txt").write_text("x", encoding="utf-8")
    result = await tool_with_vault.call({"action": "delete_folder", "path": "ToRemove"}, no_vault_ctx)
    assert result.success is True
    assert "Deleted folder" in result.content
    assert not (tmp_path / "ToRemove").exists()


@pytest.mark.asyncio
async def test_obsidian_delete_folder_missing(tool_with_vault, no_vault_ctx):
    result = await tool_with_vault.call({"action": "delete_folder", "path": "Nonexistent"}, no_vault_ctx)
    assert result.success is False


@pytest.mark.asyncio
async def test_obsidian_path_escape_rejected(tool_with_vault, no_vault_ctx):
    result = await tool_with_vault.call({"action": "read", "path": "../../../etc/passwd"}, no_vault_ctx)
    assert result.success is False


@pytest.mark.asyncio
async def test_obsidian_preview(tool_with_vault, no_vault_ctx):
    preview = await tool_with_vault.preview({"action": "read", "path": "My Note"}, no_vault_ctx)
    assert preview.tool_name == "obsidian"
    assert "read" in preview.title.lower()
    assert "My Note" in preview.summary


# --- Semantic / hybrid search ---


_VOCAB = (
    "rocket", "orbit", "cook", "pasta", "garden", "alpha", "beta", "spaceflight",
)


async def _bow_embed(texts: list[str]) -> list[list[float]]:
    out: list[list[float]] = []
    for text in texts:
        lower = text.lower()
        out.append([1.0 if token in lower else 0.0 for token in _VOCAB])
    return out


@pytest.fixture
def rag_ctx(tmp_path):
    from backend.storage.memory import InMemoryEmbeddingStore

    store = InMemoryEmbeddingStore()
    return ToolContext(
        user_id="u1",
        chat_id="c1",
        memory_store=None,
        embedding_store=store,
        embedder=_bow_embed,
    )


@pytest.fixture
def rag_tool(tmp_path):
    from backend.config import ObsidianRagConfig

    (tmp_path / "Notes").mkdir()
    (tmp_path / "Notes" / "Space.md").write_text(
        "# Space\n\nNotes about rockets and orbital spaceflight.\n",
        encoding="utf-8",
    )
    (tmp_path / "Notes" / "Food.md").write_text(
        "# Food\n\nCooking pasta recipes.\n",
        encoding="utf-8",
    )
    return ObsidianTool(
        vault_path=str(tmp_path),
        rag_config=ObsidianRagConfig(search_top_k=5, namespace="obsidian"),
        embeddings_dir=tmp_path / "emb",
    )


@pytest.mark.asyncio
async def test_obsidian_semantic_search(rag_tool, rag_ctx):
    result = await rag_tool.call(
        {"action": "search", "query": "rockets and orbits", "mode": "semantic", "limit": 5},
        rag_ctx,
    )
    assert result.success is True
    assert result.data["mode"] == "semantic"
    paths = [m["path"] for m in result.data["matches"]]
    assert paths[0] == "Notes/Space"
    assert "Notes/Space" in result.content


@pytest.mark.asyncio
async def test_obsidian_hybrid_search(rag_tool, rag_ctx):
    result = await rag_tool.call(
        {"action": "search", "query": "pasta", "mode": "hybrid", "limit": 5},
        rag_ctx,
    )
    assert result.success is True
    assert result.data["mode"] == "hybrid"
    paths = [m["path"] for m in result.data["matches"]]
    assert "Notes/Food" in paths


@pytest.mark.asyncio
async def test_obsidian_semantic_requires_embedder_falls_back_to_keyword(tmp_path):
    tool = ObsidianTool(vault_path=str(tmp_path), embeddings_dir=tmp_path / "emb")
    (tmp_path / "A.md").write_text("hello world", encoding="utf-8")
    ctx = ToolContext(user_id="u1", chat_id="c1", embedding_store=None, embedder=None)
    result = await tool.call({"action": "search", "query": "hello", "mode": "semantic"}, ctx)
    assert result.success is True
    assert result.data.get("mode") == "keyword"
    assert any(m["path"] == "A" for m in result.data["matches"])

@pytest.mark.asyncio
async def test_obsidian_semantic_empty_query_lists_notes(rag_tool, rag_ctx):
    """Empty query lists notes even when mode is semantic (no index required)."""
    result = await rag_tool.call({"action": "search", "query": "", "mode": "semantic"}, rag_ctx)
    assert result.success is True
    paths = {m["path"] for m in result.data["matches"]}
    assert "Notes/Space" in paths


@pytest.mark.asyncio
async def test_obsidian_keyword_mode_explicit(tool_with_vault, no_vault_ctx, tmp_path):
    (tmp_path / "A.md").write_text("apple banana", encoding="utf-8")
    result = await tool_with_vault.call(
        {"action": "search", "query": "banana", "mode": "keyword"},
        no_vault_ctx,
    )
    assert result.success is True
    assert result.data.get("mode") == "keyword"


@pytest.mark.asyncio
async def test_obsidian_default_mode_is_hybrid(rag_tool, rag_ctx):
    result = await rag_tool.call(
        {"action": "search", "query": "rockets", "limit": 5},
        rag_ctx,
    )
    assert result.success is True
    assert result.data.get("mode") == "hybrid"


@pytest.mark.asyncio
async def test_obsidian_empty_query_lists_notes_even_with_default_hybrid(rag_tool, rag_ctx):
    result = await rag_tool.call({"action": "search", "query": ""}, rag_ctx)
    assert result.success is True
    paths = {m["path"] for m in result.data["matches"]}
    assert "Notes/Space" in paths
    assert "Notes/Food" in paths
