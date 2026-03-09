"""Shared utilities."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from aiohttp.web_ws import WebSocketResponse


def now_iso() -> str:
    """Current UTC time as ISO 8601 string with milliseconds (e.g. 2025-03-06T12:00:00.000Z)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


class WSChannel:
    def __init__(self, ws: WebSocketResponse):
        self._ws = ws

    async def send(self, msg: dict):
        await self._ws.send_str(json.dumps(msg))

    def __aiter__(self) -> WebSocketResponse:
        return self._ws
