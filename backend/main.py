"""aiohttp application entry: load config, mount routes, run server."""

from aiohttp import web

from backend.config import load_config
from backend.routes import setup_http_routes, setup_ws_routes


def create_app(config_path: str | None = None) -> web.Application:
    """Build aiohttp app with config and routes. No auth; default user implied."""
    config = load_config(config_path)
    app = web.Application()
    app["config"] = config
    # Placeholders for injected dependencies (set when implementing stores/provider)
    # app["chat_store"] = ...
    # app["memory_store"] = ...
    # app["model_provider"] = ...
    setup_http_routes(app)
    setup_ws_routes(app)
    return app


def run_app(host: str | None = None, port: int | None = None, config_path: str | None = None) -> None:
    """Run the server. Host/port override config file if provided."""
    app = create_app(config_path)
    cfg = app["config"]
    h = host or cfg.server.host
    p = port or cfg.server.port
    web.run_app(app, host=h, port=p)


if __name__ == "__main__":
    run_app()
