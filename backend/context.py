"""Chat history context window: trim to budget, optionally summarize overflow.

Applies only to persisted chat messages (user/assistant/tool). Ephemeral
system prefix (persona, memories) and in-turn tool context are handled elsewhere.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from backend.config import ContextConfig
from backend.interfaces.model import ChatMessage


@dataclass(frozen=True)
class ContextWindowResult:
    """Result of applying the context window to chat history."""

    messages: list[ChatMessage]
    dropped_count: int
    summarized: bool


def estimate_message_chars(msg: ChatMessage) -> int:
    """Rough size proxy (chars). Good enough for soft budgets without a tokenizer."""
    n = len(msg.content or "")
    if msg.tool_calls:
        try:
            n += len(json.dumps(msg.tool_calls, ensure_ascii=False))
        except (TypeError, ValueError):
            n += sum(len(str(tc)) for tc in msg.tool_calls)
    if msg.tool_call_id:
        n += len(msg.tool_call_id)
    return n


def _safe_start_index(messages: list[ChatMessage], start: int) -> int:
    """Move start left so we do not begin mid tool-result after an assistant tool_calls."""
    if start <= 0 or start >= len(messages):
        return max(0, min(start, len(messages)))
    i = start
    while i > 0 and messages[i].role == "tool":
        i -= 1
    return i


def _fits(
        messages: list[ChatMessage],
        start: int,
        *,
        max_messages: int,
        max_chars: int,
) -> bool:
    suffix = messages[start:]
    if max_messages > 0 and len(suffix) > max_messages:
        return False
    if max_chars > 0 and sum(estimate_message_chars(m) for m in suffix) > max_chars:
        return False
    return True


def _build_extractive_summary(
        dropped: list[ChatMessage],
        *,
        per_message_chars: int,
        max_chars: int,
) -> ChatMessage | None:
    if not dropped:
        return None
    header = "Earlier conversation (truncated; older turns omitted from full context):"
    lines: list[str] = [header]
    used = len(header)
    for msg in dropped:
        role = msg.role or "unknown"
        content = (msg.content or "").replace("\n", " ").strip()
        if msg.tool_calls and not content:
            names = ", ".join(
                str(tc.get("name", "?")) for tc in msg.tool_calls if isinstance(tc, dict)
            )
            content = f"[tool_calls: {names}]"
        if per_message_chars > 0 and len(content) > per_message_chars:
            content = content[: max(0, per_message_chars - 1)] + "…"
        line = f"- {role}: {content}" if content else f"- {role}:"
        if max_chars > 0 and used + len(line) + 1 > max_chars:
            lines.append("- …")
            break
        lines.append(line)
        used += len(line) + 1
    return ChatMessage(role="system", content="\n".join(lines))


def apply_context_window(
        messages: list[ChatMessage],
        context: ContextConfig,
) -> ContextWindowResult:
    """
    Keep a recent suffix of ``messages`` within ``context.max_messages`` / ``max_chars``.

    ``max_messages`` / ``max_chars`` of 0 mean unlimited for that dimension.
    When overflow is trimmed and ``summarize_overflow`` is True, prepend one
    extractive system summary of the dropped prefix (no LLM call).
    """
    max_messages = context.max_messages
    max_chars = context.max_chars
    if not messages or (max_messages <= 0 and max_chars <= 0):
        return ContextWindowResult(messages=list(messages), dropped_count=0, summarized=False)

    # Smallest start that fits ⇒ keep as much recent history as possible.
    chosen: int | None = None
    for start in range(len(messages)):
        adj = _safe_start_index(messages, start)
        if adj < start:
            # Cut would land inside tool results; only accept the expanded start if it fits.
            if _fits(messages, adj, max_messages=max_messages, max_chars=max_chars):
                chosen = adj
                break
            continue
        if _fits(messages, start, max_messages=max_messages, max_chars=max_chars):
            chosen = start
            break

    if chosen is None:
        # Single oversized tail message (or tool block): keep it anyway.
        chosen = _safe_start_index(messages, len(messages) - 1)

    if chosen <= 0:
        return ContextWindowResult(messages=list(messages), dropped_count=0, summarized=False)

    dropped = messages[:chosen]
    kept = messages[chosen:]
    out: list[ChatMessage] = list(kept)
    summarized = False
    if context.summarize_overflow:
        summary = _build_extractive_summary(
            dropped,
            per_message_chars=context.summary_message_chars,
            max_chars=context.summary_max_chars,
        )
        if summary is not None:
            out = [summary] + out
            summarized = True
    return ContextWindowResult(messages=out, dropped_count=len(dropped), summarized=summarized)
