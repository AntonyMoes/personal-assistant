"""aiohttp application entry: load config, mount routes, run server."""

from aiohttp import web

from backend.config import load_config


@web.middleware
async def cors_middleware(request, handler):
    """Add CORS headers for local frontend development."""
    if request.method == "OPTIONS":
        return web.Response(
            status=204,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, PATCH, DELETE, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type",
                "Access-Control-Max-Age": "86400",
            },
        )
    response = await handler(request)
    response.headers["Access-Control-Allow-Origin"] = "*"
    return response


from backend.providers import create_model_provider
from backend.routes import setup_http_routes, setup_ws_routes
from backend.storage import InMemoryChatStore, InMemoryEmbeddingStore, InMemoryMemoryStore
from backend.tools import ForgetTool, RememberTool


def create_app(config_path: str | None = None) -> web.Application:
    """Build aiohttp app with config and routes. No auth; default user implied.
    If model_provider is given, it is used instead of creating one from config (e.g. tests use StubModelProvider).
    """
    config = load_config(config_path)
    app = web.Application(middlewares=[cors_middleware])
    app["config"] = config
    app["chat_store"] = InMemoryChatStore()
    app["memory_store"] = InMemoryMemoryStore()
    app["embedding_store"] = InMemoryEmbeddingStore()
    app["model_provider"] = create_model_provider(config.model)
    app["tools"] = [RememberTool(), ForgetTool()]
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
