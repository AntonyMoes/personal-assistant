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
    assert Capability.OBSIDIAN_READ in tool_with_vault.capabilities()
    assert Capability.OBSIDIAN_MODIFY in tool_with_vault.capabilities()


def test_obsidian_tool_args_schema(tool_with_vault):
    schema = tool_with_vault.args_schema()
    assert schema["type"] == "object"
    assert "action" in schema["properties"]
    assert schema["properties"]["action"]["enum"] == ["read", "search", "backlinks", "list_by_tag", "write", "delete"]
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
    assert result.data and result.data.get("path") == "Note"


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
    assert "missing or invalid 'path' for read." in result.content.lower()


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
    assert "Deleted note" in result.content
    assert not (tmp_path / "ToDelete.md").exists()


@pytest.mark.asyncio
async def test_obsidian_delete_missing_note(tool_with_vault, no_vault_ctx):
    result = await tool_with_vault.call({"action": "delete", "path": "Nonexistent"}, no_vault_ctx)
    assert result.success is False
    assert "path" in result.content.lower() or "not found" in result.content.lower() or "does not exist" in result.content.lower()


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
