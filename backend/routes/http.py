"""REST endpoints: chats, memories, models, settings."""

from aiohttp import web


async def health(_: web.Request) -> web.Response:
    return web.json_response({"status": "ok"})


async def list_chats(request: web.Request) -> web.Response:
    # TODO: get user_id from app["config"], list from ChatStore
    return web.json_response({"chats": []})


async def get_chat(request: web.Request) -> web.Response:
    chat_id = request.match_info["chat_id"]
    # TODO: load from ChatStore, return 404 if missing
    return web.json_response({"id": chat_id, "title": "", "model": "", "archived": False})


async def create_chat(request: web.Request) -> web.Response:
    # TODO: parse body, create via ChatStore
    return web.json_response({"id": "", "title": "", "model": ""}, status=201)


async def update_chat(request: web.Request) -> web.Response:
    chat_id = request.match_info["chat_id"]
    # TODO: parse body, update via ChatStore
    return web.json_response({"id": chat_id})


async def list_memories(request: web.Request) -> web.Response:
    # TODO: get user_id, list from MemoryStore
    return web.json_response({"memories": []})


async def get_memory(request: web.Request) -> web.Response:
    memory_id = request.match_info["memory_id"]
    # TODO: load from MemoryStore
    return web.json_response({"id": memory_id})


async def list_models(request: web.Request) -> web.Response:
    # TODO: get ModelProvider from app, return list_models()
    return web.json_response({"models": []})


async def get_settings(request: web.Request) -> web.Response:
    # TODO: return app["config"] permissions and defaults
    return web.json_response({"permissions": {}})


async def update_settings(request: web.Request) -> web.Response:
    # TODO: parse body, validate, persist settings
    return web.json_response({"permissions": {}})


def setup_http_routes(app: web.Application) -> None:
    """Register REST routes on the aiohttp app."""
    app.router.add_get("/health", health)
    app.router.add_get("/chats", list_chats)
    app.router.add_get("/chats/{chat_id}", get_chat)
    app.router.add_post("/chats", create_chat)
    app.router.add_patch("/chats/{chat_id}", update_chat)
    app.router.add_get("/memories", list_memories)
    app.router.add_get("/memories/{memory_id}", get_memory)
    app.router.add_get("/models", list_models)
    app.router.add_get("/settings", get_settings)
    app.router.add_patch("/settings", update_settings)
