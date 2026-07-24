"""Tests for markdown chunking and ObsidianVaultIndexer."""

from __future__ import annotations

import pytest

from backend.config import load_config
from backend.rag.chunking import chunk_markdown
from backend.rag.obsidian_index import ObsidianIndexConfig, ObsidianVaultIndexer
from backend.storage.file import FileSystemEmbeddingStore
from backend.storage.memory import InMemoryEmbeddingStore

# Fixed vocab so similar notes share nonzero cosine (unlike hash/stub zero vectors).
_VOCAB = (
    "rocket", "orbit", "cook", "pasta", "garden", "gardening",
    "alpha", "beta", "tip", "tips", "updated",
)


async def _bow_embed(texts: list[str]) -> list[list[float]]:
    out: list[list[float]] = []
    for text in texts:
        lower = text.lower()
        out.append([1.0 if token in lower else 0.0 for token in _VOCAB])
    return out


def test_chunk_markdown_by_headings():
    content = "# Title\n\nIntro para.\n\n## Section A\n\nBody A.\n\n## Section B\n\nBody B.\n"
    chunks = chunk_markdown(content, path="Notes/Doc.md", chunk_chars=1600)
    assert len(chunks) >= 2
    assert chunks[0].path == "Notes/Doc.md"
    assert chunks[0].id == "Notes/Doc.md#0"
    assert chunks[0].title == "Title"
    assert any(c.heading == "Section A" for c in chunks)
    assert "Notes/Doc.md" in chunks[0].text


def test_chunk_markdown_size_split():
    body = "word " * 500
    content = f"## Big\n\n{body}"
    chunks = chunk_markdown(content, path="Big.md", chunk_chars=200, overlap_chars=40)
    assert len(chunks) > 1
    assert all(c.heading == "Big" for c in chunks)
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))


def test_chunk_markdown_empty():
    assert chunk_markdown("   \n", path="Empty.md") == []


def test_load_obsidian_rag_config(tmp_path):
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(
        """
obsidian_rag:
  namespace: vault
  chunk_chars: 800
  chunk_overlap_chars: 50
  embed_batch_size: 16
""",
        encoding="utf-8",
    )
    config = load_config(cfg_path)
    assert config.obsidian_rag.namespace == "vault"
    assert config.obsidian_rag.chunk_chars == 800
    assert config.obsidian_rag.chunk_overlap_chars == 50
    assert config.obsidian_rag.embed_batch_size == 16


def test_load_obsidian_rag_defaults(tmp_path):
    config = load_config(tmp_path / "missing.yaml")
    assert config.obsidian_rag.namespace == "obsidian"
    assert config.obsidian_rag.chunk_chars == 1600


@pytest.fixture
def vault(tmp_path):
    (tmp_path / "Notes").mkdir()
    (tmp_path / "Notes" / "Alpha.md").write_text(
        "# Alpha\n\nAlpha discusses rockets and orbits.\n",
        encoding="utf-8",
    )
    (tmp_path / "Notes" / "Beta.md").write_text(
        "# Beta\n\nBeta is about cooking pasta.\n",
        encoding="utf-8",
    )
    # Should be skipped
    obsidian = tmp_path / ".obsidian"
    obsidian.mkdir()
    (obsidian / "workspace.md").write_text("skip me", encoding="utf-8")
    return tmp_path


@pytest.mark.asyncio
async def test_ensure_index_incremental(vault, tmp_path):
    store = InMemoryEmbeddingStore()
    indexer = ObsidianVaultIndexer(
        vault,
        store,
        _bow_embed,
        config=ObsidianIndexConfig(embed_batch_size=2, chunk_chars=1600),
        embeddings_dir=tmp_path / "emb",
    )
    stats = await indexer.ensure_index()
    assert stats.scanned == 2
    assert stats.indexed == 2
    assert stats.skipped == 0
    assert stats.chunks_upserted >= 2

    # Unchanged → skip
    stats2 = await indexer.ensure_index()
    assert stats2.indexed == 0
    assert stats2.skipped == 2

    query = (await _bow_embed(["rockets and orbits"]))[0]
    hits = await store.search("obsidian", query, k=5)
    assert hits
    assert hits[0][2].get("path") == "Notes/Alpha.md"


@pytest.mark.asyncio
async def test_reindex_path_and_remove(vault, tmp_path):
    store = InMemoryEmbeddingStore()
    indexer = ObsidianVaultIndexer(
        vault,
        store,
        _bow_embed,
        embeddings_dir=tmp_path / "emb",
    )
    await indexer.ensure_index()

    alpha = vault / "Notes" / "Alpha.md"
    alpha.write_text("# Alpha\n\nUpdated: gardening tips.\n", encoding="utf-8")
    stats = await indexer.reindex_path("Notes/Alpha.md")
    assert stats.indexed == 1
    assert stats.chunks_upserted >= 1

    query = (await _bow_embed(["gardening tips"]))[0]
    hits = await store.search("obsidian", query, k=3)
    assert hits
    assert hits[0][2].get("path") == "Notes/Alpha.md"

    removed = await indexer.remove_path("Notes/Beta")
    assert removed.removed == 1
    all_hits = await store.search("obsidian", (await _bow_embed(["pasta cooking"]))[0], k=10)
    assert all(h[2].get("path") != "Notes/Beta.md" for h in all_hits)


@pytest.mark.asyncio
async def test_ensure_index_removes_deleted_file(vault, tmp_path):
    store = InMemoryEmbeddingStore()
    indexer = ObsidianVaultIndexer(
        vault,
        store,
        _bow_embed,
        embeddings_dir=tmp_path / "emb",
    )
    await indexer.ensure_index()
    (vault / "Notes" / "Beta.md").unlink()
    stats = await indexer.ensure_index()
    assert stats.removed == 1
    assert stats.skipped == 1  # Alpha unchanged


@pytest.mark.asyncio
async def test_full_reindex_with_file_store(vault, tmp_path):
    emb_dir = tmp_path / "embeddings"
    store = FileSystemEmbeddingStore(emb_dir)
    indexer = ObsidianVaultIndexer(
        vault,
        store,
        _bow_embed,
        embeddings_dir=emb_dir,
    )
    await indexer.ensure_index()
    stats = await indexer.reindex()
    assert stats.indexed == 2
    assert (emb_dir / "obsidian.manifest.json").is_file()
    store2 = FileSystemEmbeddingStore(emb_dir)
    results = await store2.search("obsidian", (await _bow_embed(["rockets"]))[0], k=3)
    assert len(results) >= 1
    assert results[0][2].get("path") == "Notes/Alpha.md"


@pytest.mark.asyncio
async def test_max_files_cap(vault, tmp_path):
    store = InMemoryEmbeddingStore()
    indexer = ObsidianVaultIndexer(
        vault,
        store,
        _bow_embed,
        embeddings_dir=tmp_path / "emb",
    )
    stats = await indexer.ensure_index(max_files=1)
    assert stats.indexed == 1
    stats2 = await indexer.ensure_index(max_files=10)
    assert stats2.indexed == 1
    assert stats2.skipped == 1
