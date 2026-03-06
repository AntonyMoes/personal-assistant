"""HTTP and WebSocket route handlers."""

from backend.routes.http import setup_http_routes
from backend.routes.ws import setup_ws_routes

__all__ = ["setup_http_routes", "setup_ws_routes"]
