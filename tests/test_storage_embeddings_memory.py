"""Tests for EmbeddingStore (in-memory and file backends share behavior)."""

import pytest

from backend.config import StorageConfig
from backend.storage import create_embedding_store
from backend.storage.file import FileSystemEmbeddingStore
from backend.storage.memory import InMemoryEmbeddingStore


@pytest.fixture(params=["memory", "file"])
def store(request, tmp_path):
    if request.param == "memory":
        return InMemoryEmbeddingStore()
    return FileSystemEmbeddingStore(tmp_path)


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


@pytest.mark.asyncio
async def test_fs_embedding_persistence(tmp_path):
    store = FileSystemEmbeddingStore(tmp_path)
    await store.upsert("obsidian", "Notes/Foo.md#0", [1.0, 0.0, 0.0], {"path": "Notes/Foo.md"})
    await store.upsert("obsidian", "Notes/Bar.md#0", [0.0, 1.0, 0.0], {"path": "Notes/Bar.md"})

    store2 = FileSystemEmbeddingStore(tmp_path)
    results = await store2.search("obsidian", [1.0, 0.0, 0.0], k=2)
    assert len(results) == 2
    assert results[0][0] == "Notes/Foo.md#0"
    assert results[0][2]["path"] == "Notes/Foo.md"


@pytest.mark.asyncio
async def test_fs_embedding_rejects_bad_namespace(tmp_path):
    store = FileSystemEmbeddingStore(tmp_path)
    with pytest.raises(ValueError):
        await store.upsert("../escape", "id1", [1.0])
    with pytest.raises(ValueError):
        await store.upsert("a/b", "id1", [1.0])


@pytest.mark.asyncio
async def test_upsert_many_and_replace_many(store):
    await store.upsert_many(
        "ns1",
        [
            ("a", [1.0, 0.0], {"path": "A.md"}),
            ("b", [0.0, 1.0], {"path": "B.md"}),
        ],
    )
    results = await store.search("ns1", [1.0, 0.0], k=5)
    assert {r[0] for r in results} == {"a", "b"}

    await store.replace_many(
        "ns1",
        delete_ids=["a"],
        upserts=[("a2", [1.0, 0.0], {"path": "A.md"}), ("c", [0.5, 0.5], {"path": "C.md"})],
    )
    results = await store.search("ns1", [1.0, 0.0], k=5)
    ids = {r[0] for r in results}
    assert "a" not in ids
    assert "a2" in ids and "b" in ids and "c" in ids


@pytest.mark.asyncio
async def test_fs_batched_defers_disk_write(tmp_path):
    store = FileSystemEmbeddingStore(tmp_path)
    index_path = tmp_path / "ns1" / "index.json"
    with store.batched():
        await store.upsert("ns1", "id1", [1.0, 0.0])
        await store.upsert("ns1", "id2", [0.0, 1.0])
        # Still deferred — file should not exist yet (or be stale empty)
        assert not index_path.exists()
    assert index_path.is_file()
    # Compact JSON (no pretty indent)
    raw = index_path.read_text(encoding="utf-8")
    assert "\n  " not in raw
    store2 = FileSystemEmbeddingStore(tmp_path)
    results = await store2.search("ns1", [1.0, 0.0], k=2)
    assert len(results) == 2


@pytest.mark.asyncio
async def test_fs_replace_many_one_write(tmp_path, monkeypatch):
    store = FileSystemEmbeddingStore(tmp_path)
    writes = {"n": 0}
    orig = store._write_namespace

    def counting_write(namespace, items):
        writes["n"] += 1
        return orig(namespace, items)

    monkeypatch.setattr(store, "_write_namespace", counting_write)
    await store.replace_many(
        "ns1",
        delete_ids=["gone"],
        upserts=[
            ("a", [1.0, 0.0], None),
            ("b", [0.0, 1.0], None),
            ("c", [0.5, 0.5], None),
        ],
    )
    assert writes["n"] == 1


def test_create_embedding_store_respects_backend(tmp_path):
    mem = create_embedding_store(StorageConfig(backend="memory"))
    assert isinstance(mem, InMemoryEmbeddingStore)

    file_cfg = StorageConfig(
        backend="file",
        base_path=str(tmp_path),
        embeddings_dir=str(tmp_path / "embeddings"),
    )
    fs = create_embedding_store(file_cfg)
    assert isinstance(fs, FileSystemEmbeddingStore)
