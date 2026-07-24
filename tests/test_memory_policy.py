"""Tests for backend.memory_policy: profile + keyword/recency selection."""

from backend.config import MemoryInjectionConfig
from backend.interfaces.model import ChatMessage
from backend.interfaces.storage import MemoryRecord
from backend.memory_policy import (
    format_memory_block,
    latest_user_query,
    score_memory,
    select_memories_for_injection,
    select_profile,
    select_retrieved,
    tokenize_query,
)


def _mem(key: str, content: str, *, mid: str | None = None, updated_at: str = "2024-01-01T00:00:00Z") -> MemoryRecord:
    return MemoryRecord(
        id=mid or key,
        user_id="u1",
        key=key,
        content=content,
        created_at=updated_at,
        updated_at=updated_at,
    )


def test_tokenize_drops_stopwords():
    tokens = tokenize_query("What is my favorite color please?")
    assert "favorite" in tokens
    assert "color" in tokens
    assert "what" not in tokens
    assert "my" not in tokens


def test_select_profile_respects_allowlist_order():
    memories = [
        _mem("timezone", "UTC"),
        _mem("name", "Ada"),
        _mem("favorite_color", "blue"),
    ]
    profile = select_profile(memories, ["name", "timezone", "locale"])
    assert [m.key for m in profile] == ["name", "timezone"]


def test_select_retrieved_prefers_keyword_overlap():
    # Newest first (as list_memories returns).
    memories = [
        _mem("project_alpha", "shipping soon", mid="1", updated_at="2024-06-01"),
        _mem("favorite_color", "blue", mid="2", updated_at="2024-05-01"),
        _mem("birthday", "March 3", mid="3", updated_at="2024-04-01"),
    ]
    hit = select_retrieved(memories, "what is my favorite color?", top_k=1)
    assert len(hit) == 1
    assert hit[0].key == "favorite_color"


def test_select_retrieved_falls_back_to_recency():
    memories = [
        _mem("a", "one", mid="1", updated_at="2024-06-01"),
        _mem("b", "two", mid="2", updated_at="2024-05-01"),
        _mem("c", "three", mid="3", updated_at="2024-04-01"),
    ]
    hit = select_retrieved(memories, "", top_k=2)
    assert [m.key for m in hit] == ["a", "b"]


def test_select_memories_excludes_profile_from_retrieved():
    memories = [
        _mem("name", "Ada", mid="p", updated_at="2024-06-01"),
        _mem("favorite_color", "blue", mid="r", updated_at="2024-05-01"),
        _mem("pet", "cat named Ada", mid="x", updated_at="2024-04-01"),
    ]
    cfg = MemoryInjectionConfig(profile_keys=["name"], retrieve_top_k=2)
    selection = select_memories_for_injection(memories, "tell me about Ada", cfg)
    assert [m.key for m in selection.profile] == ["name"]
    assert all(m.key != "name" for m in selection.retrieved)
    block = format_memory_block(selection)
    assert block is not None
    assert "Profile:" in block
    assert "- name: Ada" in block
    assert "Relevant:" in block


def test_format_memory_block_none_when_empty():
    from backend.memory_policy import MemorySelection

    assert format_memory_block(MemorySelection(profile=[], retrieved=[])) is None


def test_format_flat_when_no_profile():
    selection = select_memories_for_injection(
        [_mem("favorite_color", "blue")],
        "color",
        MemoryInjectionConfig(profile_keys=[], retrieve_top_k=5),
    )
    block = format_memory_block(selection)
    assert block is not None
    assert "Profile:" not in block
    assert "- favorite_color: blue" in block


def test_latest_user_query_from_string():
    assert latest_user_query("hello", []) == "hello"


def test_latest_user_query_from_history():
    history = [
        ChatMessage("user", "old"),
        ChatMessage("assistant", "ok"),
        ChatMessage("user", "latest question"),
    ]
    assert latest_user_query(None, history) == "latest question"


def test_score_key_beats_content_only():
    key_hit = _mem("color", "irrelevant")
    content_hit = _mem("misc", "favorite color is blue")
    q = tokenize_query("color")
    assert score_memory(key_hit, q, recency_rank=5) > score_memory(content_hit, q, recency_rank=0)
