"""Markdown chunking for vault RAG (heading-aware, size fallback)."""

from __future__ import annotations

import re
from dataclasses import dataclass


_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)


@dataclass(frozen=True)
class Chunk:
    """One embeddable unit from a markdown note."""

    id: str  # e.g. Notes/Foo.md#0
    text: str  # text sent to the embedder (includes path/heading context)
    path: str  # vault-relative path with .md
    heading: str  # nearest heading, or ""
    chunk_index: int
    title: str  # note title (first heading or file stem)


def chunk_markdown(
        content: str,
        *,
        path: str,
        chunk_chars: int = 1600,
        overlap_chars: int = 200,
) -> list[Chunk]:
    """
    Split markdown into chunks.

    Prefer heading boundaries; oversized sections are window-split with overlap.
    Embed text is prefixed with path (and heading when present) for better retrieval.
    """
    path = path.replace("\\", "/").strip()
    if chunk_chars < 1:
        chunk_chars = 1600
    overlap_chars = max(0, min(overlap_chars, chunk_chars - 1))

    sections = _split_by_headings(content)
    title = _note_title(sections, path)

    drafts: list[tuple[str, str]] = []  # (heading, body)
    for heading, body in sections:
        body = body.strip()
        if not body and not heading:
            continue
        if not body:
            continue
        for piece in _window_split(body, chunk_chars, overlap_chars):
            piece = piece.strip()
            if piece:
                drafts.append((heading, piece))

    chunks: list[Chunk] = []
    for i, (heading, body) in enumerate(drafts):
        embed_text = _embed_text(path, heading, body)
        chunks.append(
            Chunk(
                id=f"{path}#{i}",
                text=embed_text,
                path=path,
                heading=heading,
                chunk_index=i,
                title=title,
            )
        )
    return chunks


def _note_title(sections: list[tuple[str, str]], path: str) -> str:
    for heading, _ in sections:
        if heading:
            return heading
    stem = path.rsplit("/", 1)[-1]
    if stem.lower().endswith(".md"):
        stem = stem[:-3]
    return stem or path


def _split_by_headings(content: str) -> list[tuple[str, str]]:
    """Return [(heading_text_or_empty, section_body), ...] in document order."""
    text = content or ""
    matches = list(_HEADING_RE.finditer(text))
    if not matches:
        return [("", text)]

    sections: list[tuple[str, str]] = []
    # Preamble before first heading
    first = matches[0]
    preamble = text[: first.start()]
    if preamble.strip():
        sections.append(("", preamble))

    for i, match in enumerate(matches):
        heading = match.group(2).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections.append((heading, text[start:end]))
    return sections


def _window_split(text: str, size: int, overlap: int) -> list[str]:
    if len(text) <= size:
        return [text]
    parts: list[str] = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + size, n)
        # Prefer breaking on a newline near the end of the window
        if end < n:
            break_at = text.rfind("\n", start + size // 2, end)
            if break_at > start:
                end = break_at + 1
        parts.append(text[start:end])
        if end >= n:
            break
        start = max(start + 1, end - overlap)
    return parts


def _embed_text(path: str, heading: str, body: str) -> str:
    if heading:
        return f"{path} > {heading}\n{body}"
    return f"{path}\n{body}"
