"""Memory injection policy: always-on profile + keyword/recency retrieval.

Keeps the ephemeral system memory block small. Embedding-based retrieval can
replace ``score_memory`` / ``select_retrieved`` later without changing callers.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Sequence

from backend.config import MemoryInjectionConfig
from backend.interfaces.storage import MemoryRecord

_TOKEN_RE = re.compile(r"[a-z0-9_]+", re.IGNORECASE)

# Light English stopwords so queries like "what is my ..." do not flood matches.
_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "to",
        "of",
        "and",
        "or",
        "in",
        "on",
        "for",
        "it",
        "its",
        "that",
        "this",
        "with",
        "as",
        "at",
        "by",
        "from",
        "my",
        "me",
        "i",
        "you",
        "your",
        "do",
        "does",
        "did",
        "have",
        "has",
        "had",
        "what",
        "when",
        "where",
        "who",
        "whom",
        "which",
        "how",
        "why",
        "can",
        "could",
        "would",
        "should",
        "will",
        "please",
        "tell",
        "about",
        "into",
        "than",
        "then",
        "so",
        "if",
        "not",
        "no",
        "yes",
        "just",
        "also",
        "any",
        "all",
    }
)


@dataclass(frozen=True)
class MemorySelection:
    """Memories chosen for one turn's system injection."""

    profile: list[MemoryRecord]
    retrieved: list[MemoryRecord]

    @property
    def all(self) -> list[MemoryRecord]:
        return list(self.profile) + list(self.retrieved)


def tokenize_query(text: str) -> list[str]:
    """Lowercase alnum/underscore tokens; drop stopwords and single-char noise."""
    if not text:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for raw in _TOKEN_RE.findall(text.lower()):
        if raw in _STOPWORDS or len(raw) < 2:
            continue
        if raw not in seen:
            seen.add(raw)
            out.append(raw)
    return out


def score_memory(
        memory: MemoryRecord,
        query_tokens: Sequence[str],
        *,
        recency_rank: int,
) -> float:
    """
    Higher is better. Keyword overlap (key weighted 2x) plus small recency term.

    ``recency_rank`` 0 = most recently updated among candidates.
    """
    if not query_tokens:
        return 1.0 / (1.0 + recency_rank)

    # Split key on _/- so favorite_color matches query tokens "favorite" and "color".
    key_norm = memory.key.lower().replace("-", "_")
    key_parts = {
        t
        for part in key_norm.split("_")
        for t in _TOKEN_RE.findall(part)
        if t not in _STOPWORDS and len(t) >= 2
    }
    # Also keep the full underscored key as a token for exact key queries.
    if key_norm and len(key_norm) >= 2:
        key_parts.add(key_norm)
    content_parts = {
        t
        for t in _TOKEN_RE.findall(memory.content.lower())
        if t not in _STOPWORDS and len(t) >= 2
    }
    key_hits = sum(1 for t in query_tokens if t in key_parts)
    content_hits = sum(1 for t in query_tokens if t in content_parts and t not in key_parts)
    overlap = 2.0 * key_hits + 1.0 * content_hits
    recency = 1.0 / (1.0 + recency_rank)
    return overlap * 10.0 + recency


def select_profile(
        memories: Sequence[MemoryRecord],
        profile_keys: Sequence[str],
) -> list[MemoryRecord]:
    """Return memories whose keys are in ``profile_keys``, in allowlist order."""
    by_key = {m.key: m for m in memories}
    out: list[MemoryRecord] = []
    for key in profile_keys:
        key_ = key.strip()
        if not key_:
            continue
        m = by_key.get(key_)
        if m is not None:
            out.append(m)
    return out


def select_retrieved(
        memories: Sequence[MemoryRecord],
        query: str,
        *,
        top_k: int,
        exclude_ids: set[str] | None = None,
) -> list[MemoryRecord]:
    """
    Top-k by keyword overlap with ``query``, then recency.

    Candidates are assumed newest-first (as ``list_memories`` returns). When the
    query has no tokens, falls back to most recent ``top_k``.
    """
    if top_k <= 0:
        return []
    exclude = exclude_ids or set()
    candidates = [m for m in memories if m.id not in exclude]
    if not candidates:
        return []

    query_tokens = tokenize_query(query)
    scored: list[tuple[float, int, MemoryRecord]] = []
    for rank, memory in enumerate(candidates):
        s = score_memory(memory, query_tokens, recency_rank=rank)
        scored.append((s, rank, memory))
    # Higher score first; stable on equal score via recency rank (lower better).
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [m for _, _, m in scored[:top_k]]


def select_memories_for_injection(
        memories: Sequence[MemoryRecord],
        query: str,
        config: MemoryInjectionConfig,
) -> MemorySelection:
    """Split always-on profile vs retrieved top-k for one turn."""
    profile = select_profile(memories, config.profile_keys)
    profile_ids = {m.id for m in profile}
    retrieved = select_retrieved(
        memories,
        query,
        top_k=config.retrieve_top_k,
        exclude_ids=profile_ids,
    )
    return MemorySelection(profile=profile, retrieved=retrieved)


def format_memory_block(selection: MemorySelection) -> str | None:
    """Format profile + retrieved as one system block, or None if empty."""
    if not selection.profile and not selection.retrieved:
        return None

    def _lines(items: Sequence[MemoryRecord]) -> list[str]:
        return [f"- {m.key}: {m.content}" for m in items]

    parts: list[str] = ["Stored memories (use when relevant):"]
    if selection.profile:
        parts.append("Profile:")
        parts.extend(_lines(selection.profile))
    if selection.retrieved:
        if selection.profile:
            parts.append("Relevant:")
        parts.extend(_lines(selection.retrieved))
    return "\n".join(parts)


def latest_user_query(
        user_content: str | None,
        history: Sequence,
) -> str:
    """Query text for retrieval: new user message, else last user turn in history."""
    if isinstance(user_content, str) and user_content.strip():
        return user_content
    for msg in reversed(history):
        role = getattr(msg, "role", None)
        content = getattr(msg, "content", None) or ""
        if role == "user" and content.strip():
            return content
    return ""
