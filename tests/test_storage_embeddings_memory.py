"""Tests for InMemoryEmbeddingStore."""

import pytest

from backend.storage.memory import InMemoryEmbeddingStore


@pytest.fixture
def store():
    return InMemoryEmbeddingStore()


@pytest.mark.asyncio
async def test_upsert_and_search(store):
    await store.upsert("ns1", "id1", [1.0, 0.0, 0.0], {"tag": "a"})
    await store.upsert("ns1", "id2", [0.9, 0.1, 0.0], {"tag": "b"})
    # Query same as id1 should score 1.0 for id1
    results = await store.search("ns1", [1.0, 0.0, 0.0], k=2)
    assert len(results) == 2
    assert results[0][0] == "id1"
    assert results[0][1] == pytest.approx(1.0)
    assert results[1][0] == "id2"
    assert results[1][1] < 1.0


@pytest.mark.asyncio
async def test_search_empty_namespace(store):
    results = await store.search("empty", [1.0, 0.0], k=5)
    assert results == []


@pytest.mark.asyncio
async def test_search_filter_metadata(store):
    await store.upsert("ns1", "a", [1.0, 0.0], {"env": "prod"})
    await store.upsert("ns1", "b", [0.0, 1.0], {"env": "dev"})
    results = await store.search("ns1", [1.0, 0.0], k=5, filter_metadata={"env": "prod"})
    assert len(results) == 1
    assert results[0][0] == "a"
    assert results[0][2]["env"] == "prod"


@pytest.mark.asyncio
async def test_search_respects_k(store):
    await store.upsert("ns1", "1", [1.0, 0.0])
    await store.upsert("ns1", "2", [0.9, 0.0])
    await store.upsert("ns1", "3", [0.8, 0.0])
    results = await store.search("ns1", [1.0, 0.0], k=2)
    assert len(results) == 2
    assert [r[0] for r in results] == ["1", "2"]


@pytest.mark.asyncio
async def test_delete(store):
    await store.upsert("ns1", "id1", [1.0, 0.0])
    ok = await store.delete("ns1", "id1")
    assert ok is True
    results = await store.search("ns1", [1.0, 0.0], k=5)
    assert results == []
    assert await store.delete("ns1", "id1") is False
    assert await store.delete("ns1", "nonexistent") is False


@pytest.mark.asyncio
async def test_delete_namespace(store):
    await store.upsert("ns1", "a", [1.0, 0.0])
    await store.upsert("ns1", "b", [0.0, 1.0])
    await store.upsert("ns2", "c", [0.0, 0.0, 1.0])
    await store.delete_namespace("ns1")
    assert await store.search("ns1", [1.0, 0.0], k=5) == []
    results = await store.search("ns2", [0.0, 0.0, 1.0], k=5)
    assert len(results) == 1
    assert results[0][0] == "c"


@pytest.mark.asyncio
async def test_upsert_overwrites(store):
    await store.upsert("ns1", "id1", [1.0, 0.0], {"v": 1})
    await store.upsert("ns1", "id1", [0.0, 1.0], {"v": 2})
    results = await store.search("ns1", [0.0, 1.0], k=5)
    assert len(results) == 1
    assert results[0][0] == "id1"
    assert results[0][2]["v"] == 2
