"""Shared utilities."""

from __future__ import annotations

from datetime import datetime, timezone


def now_iso() -> str:
    """Current UTC time as ISO 8601 string with milliseconds (e.g. 2025-03-06T12:00:00.000Z)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
