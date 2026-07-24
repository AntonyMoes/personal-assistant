"""Incremental Obsidian vault indexer: chunk → embed → EmbeddingStore upsert."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable

from backend.interfaces.storage import EmbeddingStore
from backend.rag.chunking import Chunk, chunk_markdown

logger = logging.getLogger(__name__)

EmbedFn = Callable[[list[str]], Awaitable[list[list[float]]]]


@dataclass
class IndexStats:
    """Result of an index / ensure / remove operation."""

    scanned: int = 0
    indexed: int = 0
    skipped: int = 0
    removed: int = 0
    chunks_upserted: int = 0


@dataclass
class ObsidianIndexConfig:
    """Knobs for vault chunking and embedding batches."""

    namespace: str = "obsidian"
    chunk_chars: int = 1600
    chunk_overlap_chars: int = 200
    embed_batch_size: int = 64
    # Directory names to skip anywhere under the vault (case-sensitive).
    skip_dir_names: tuple[str, ...] = (".obsidian", ".trash", ".git")

    @classmethod
    def from_rag_config(cls, rag: Any) -> ObsidianIndexConfig:
        """Build from `config.obsidian_rag` (ObsidianRagConfig)."""
        return cls(
            namespace=str(getattr(rag, "namespace", "obsidian") or "obsidian"),
            chunk_chars=int(getattr(rag, "chunk_chars", 1600)),
            chunk_overlap_chars=int(getattr(rag, "chunk_overlap_chars", 200)),
            embed_batch_size=int(getattr(rag, "embed_batch_size", 64)),
        )


def _rel_md_path(vault: Path, path: Path) -> str:
    return str(path.relative_to(vault)).replace("\\", "/")


def _should_skip(path: Path, vault: Path, skip_dir_names: tuple[str, ...]) -> bool:
    try:
        rel = path.relative_to(vault)
    except ValueError:
        return True
    return any(part in skip_dir_names for part in rel.parts)


class ObsidianVaultIndexer:
    """
    Maintain embedding vectors for vault markdown notes.

    Manifest (path → mtime + chunk ids) lives next to the embeddings root so
    unchanged files are not re-embedded. Does not wire into ObsidianTool yet.
    """

    def __init__(
            self,
            vault_path: str | Path,
            embedding_store: EmbeddingStore,
            embedder: EmbedFn,
            *,
            config: ObsidianIndexConfig | None = None,
            manifest_path: str | Path | None = None,
            embeddings_dir: str | Path | None = None,
    ) -> None:
        self._vault = Path(vault_path).resolve()
        self._store = embedding_store
        self._embed = embedder
        self._config = config or ObsidianIndexConfig()
        ns = self._config.namespace
        if manifest_path is not None:
            self._manifest_path = Path(manifest_path)
        elif embeddings_dir is not None:
            # Sibling of namespace folder: embeddings/obsidian.manifest.json
            self._manifest_path = Path(embeddings_dir).resolve() / f"{ns}.manifest.json"
        else:
            self._manifest_path = None
        self._manifest: dict[str, Any] = self._load_manifest()

    @property
    def namespace(self) -> str:
        return self._config.namespace

    @property
    def vault(self) -> Path:
        return self._vault

    def _load_manifest(self) -> dict[str, Any]:
        if self._manifest_path is None or not self._manifest_path.is_file():
            return {"files": {}}
        try:
            raw = json.loads(self._manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"files": {}}
        if not isinstance(raw, dict):
            return {"files": {}}
        files = raw.get("files")
        if not isinstance(files, dict):
            return {"files": {}}
        return {"files": files}

    def _save_manifest(self) -> None:
        if self._manifest_path is None:
            return
        self._manifest_path.parent.mkdir(parents=True, exist_ok=True)
        self._manifest_path.write_text(
            json.dumps(self._manifest, indent=2),
            encoding="utf-8",
        )

    def _list_md_files(self) -> list[Path]:
        if not self._vault.is_dir():
            return []
        files: list[Path] = []
        for path in self._vault.rglob("*.md"):
            if path.is_file() and not _should_skip(path, self._vault, self._config.skip_dir_names):
                files.append(path)
        files.sort(key=lambda p: _rel_md_path(self._vault, p))
        return files

    async def ensure_index(self, *, max_files: int | None = None) -> IndexStats:
        """Incrementally index new/changed notes; drop deleted paths. Caps work if max_files set."""
        stats = IndexStats()
        md_files = self._list_md_files()
        stats.scanned = len(md_files)
        on_disk = {_rel_md_path(self._vault, p): p for p in md_files}

        # Remove index entries for deleted notes
        for rel in list(self._manifest.get("files", {}).keys()):
            if rel not in on_disk:
                await self._remove_rel(rel)
                stats.removed += 1

        pending: list[tuple[str, Path]] = []
        for rel, path in on_disk.items():
            mtime = path.stat().st_mtime
            entry = self._manifest.get("files", {}).get(rel)
            if entry is not None and float(entry.get("mtime", -1)) == mtime:
                stats.skipped += 1
                continue
            pending.append((rel, path))

        if max_files is not None and max_files >= 0:
            pending = pending[:max_files]

        for rel, path in pending:
            n = await self._index_file(rel, path)
            stats.indexed += 1
            stats.chunks_upserted += n

        self._save_manifest()
        return stats

    async def reindex(self) -> IndexStats:
        """Full rebuild: clear namespace + manifest, then index all notes."""
        await self._store.delete_namespace(self._config.namespace)
        self._manifest = {"files": {}}
        self._save_manifest()
        return await self.ensure_index()

    async def reindex_path(self, rel_path: str) -> IndexStats:
        """Re-chunk and re-embed a single note (vault-relative path)."""
        stats = IndexStats(scanned=1)
        rel = rel_path.replace("\\", "/").strip()
        if not rel.lower().endswith(".md"):
            rel = f"{rel}.md"
        path = (self._vault / rel).resolve()
        try:
            path.relative_to(self._vault)
        except ValueError:
            return stats
        if not path.is_file():
            await self._remove_rel(rel)
            stats.removed = 1
            self._save_manifest()
            return stats
        if _should_skip(path, self._vault, self._config.skip_dir_names):
            return stats
        n = await self._index_file(rel, path)
        stats.indexed = 1
        stats.chunks_upserted = n
        self._save_manifest()
        return stats

    async def remove_path(self, rel_path: str) -> IndexStats:
        """Delete all chunks for a note from the store and manifest."""
        rel = rel_path.replace("\\", "/").strip()
        if not rel.lower().endswith(".md"):
            rel = f"{rel}.md"
        stats = IndexStats()
        existed = rel in self._manifest.get("files", {})
        await self._remove_rel(rel)
        if existed:
            stats.removed = 1
        self._save_manifest()
        return stats

    async def _remove_rel(self, rel: str) -> None:
        entry = self._manifest.get("files", {}).pop(rel, None)
        chunk_ids = list((entry or {}).get("chunk_ids") or [])
        for cid in chunk_ids:
            await self._store.delete(self._config.namespace, cid)

    async def _index_file(self, rel: str, path: Path) -> int:
        """Replace chunks for one file. Returns number of chunks upserted."""
        await self._remove_rel(rel)
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            logger.warning("Failed to read %s: %s", rel, e)
            return 0

        mtime = path.stat().st_mtime
        chunks = chunk_markdown(
            content,
            path=rel,
            chunk_chars=self._config.chunk_chars,
            overlap_chars=self._config.chunk_overlap_chars,
        )
        if not chunks:
            self._manifest.setdefault("files", {})[rel] = {
                "mtime": mtime,
                "chunk_ids": [],
            }
            return 0

        await self._embed_and_upsert(chunks, mtime)
        self._manifest.setdefault("files", {})[rel] = {
            "mtime": mtime,
            "chunk_ids": [c.id for c in chunks],
        }
        return len(chunks)

    async def _embed_and_upsert(self, chunks: list[Chunk], mtime: float) -> None:
        batch_size = max(1, self._config.embed_batch_size)
        ns = self._config.namespace
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i : i + batch_size]
            vectors = await self._embed([c.text for c in batch])
            if len(vectors) != len(batch):
                raise RuntimeError(
                    f"embedder returned {len(vectors)} vectors for {len(batch)} texts"
                )
            for chunk, vector in zip(batch, vectors):
                body = chunk.text.split("\n", 1)[-1] if "\n" in chunk.text else chunk.text
                snippet = body.replace("\n", " ").strip()[:240]
                meta = {
                    "path": chunk.path,
                    "heading": chunk.heading,
                    "chunk_index": chunk.chunk_index,
                    "title": chunk.title,
                    "mtime": mtime,
                    "snippet": snippet,
                }
                await self._store.upsert(ns, chunk.id, vector, meta)
