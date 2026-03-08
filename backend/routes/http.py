"""REST endpoints: chats, memories, models, settings."""

from aiohttp import web

DEFAULT_CHAT_TITLE = "New chat"


def _chat_to_json(chat) -> dict:
    return {
        "id": chat.id,
        "title": chat.title,
        "model": chat.model,
        "archived": chat.archived,
        "created_at": chat.created_at,
        "updated_at": chat.updated_at,
    }


def _memory_to_json(memory) -> dict:
    return {
        "id": memory.id,
        "user_id": memory.user_id,
        "key": memory.key,
        "content": memory.content,
        "created_at": memory.created_at,
        "updated_at": memory.updated_at,
    }


async def health(_: web.Request) -> web.Response:
    return web.json_response({"status": "ok"})


async def list_chats(request: web.Request) -> web.Response:
    store = request.app["chat_store"]
    user_id = request.app["config"].app.default_user_id
    q = request.query
    archived = None
    if "archived" in q:
        archived = q["archived"].lower() in ("true", "1", "yes")
    sort = q.get("sort", "updated_at")
    order = q.get("order", "desc")
    try:
        limit = min(max(1, int(q.get("limit", 100))), 500)
    except (TypeError, ValueError):
        limit = 100
    try:
        offset = max(0, int(q.get("offset", 0)))
    except (TypeError, ValueError):
        offset = 0
    chats = await store.list_chats(
        user_id, archived=archived, sort=sort, order=order, limit=limit, offset=offset
    )
    return web.json_response({"chats": [_chat_to_json(c) for c in chats]})


async def get_chat(request: web.Request) -> web.Response:
    chat_id = request.match_info["chat_id"]
    store = request.app["chat_store"]
    chat = await store.get_chat(chat_id)
    if not chat:
        return web.json_response({"error": "Not found"}, status=404)
    return web.json_response(_chat_to_json(chat))


async def get_chat_messages(request: web.Request) -> web.Response:
    chat_id = request.match_info["chat_id"]
    store = request.app["chat_store"]
    chat = await store.get_chat(chat_id)
    if not chat:
        return web.json_response({"error": "Not found"}, status=404)
    messages = await store.get_chat_messages(chat_id)
    return web.json_response({"messages": messages})


async def create_chat(request: web.Request) -> web.Response:
    try:
        body = await request.json() if request.body_exists else {}
    except Exception:
        body = {}
    if not isinstance(body, dict):
        body = {}
    title = body.get("title")
    if not isinstance(title, str) or not title.strip():
        title = DEFAULT_CHAT_TITLE
    else:
        title = title.strip()
    model = body.get("model")
    if not isinstance(model, str) or not model.strip():
        model = request.app["config"].model.default_model
    else:
        model = model.strip()
    store = request.app["chat_store"]
    user_id = request.app["config"].app.default_user_id
    chat = await store.create_chat(user_id, title=title, model=model)
    return web.json_response(_chat_to_json(chat), status=201)


async def update_chat(request: web.Request) -> web.Response:
    chat_id = request.match_info["chat_id"]
    try:
        body = await request.json() if request.body_exists else {}
    except Exception:
        body = {}
    if not isinstance(body, dict):
        body = {}
    store = request.app["chat_store"]
    chat = await store.get_chat(chat_id)
    if not chat:
        return web.json_response({"error": "Not found"}, status=404)
    title = body.get("title")
    if title is not None:
        title = title.strip() if isinstance(title, str) else None
    model = body.get("model")
    if model is not None:
        model = model.strip() if isinstance(model, str) else None
    archived = body.get("archived")
    if archived is not None and not isinstance(archived, bool):
        archived = None
    updated = await store.update_chat(
        chat_id, title=title, model=model, archived=archived
    )
    if not updated:
        return web.json_response({"error": "Not found"}, status=404)
    return web.json_response(_chat_to_json(updated))


async def delete_chat(request: web.Request) -> web.Response:
    chat_id = request.match_info["chat_id"]
    store = request.app["chat_store"]
    ok = await store.delete_chat(chat_id)
    if not ok:
        return web.json_response({"error": "Not found"}, status=404)
    return web.Response(status=204)


async def list_memories(request: web.Request) -> web.Response:
    store = request.app["memory_store"]
    user_id = request.app["config"].app.default_user_id
    q = request.query
    try:
        limit = min(max(1, int(q.get("limit", 100))), 500)
    except (TypeError, ValueError):
        limit = 100
    try:
        offset = max(0, int(q.get("offset", 0)))
    except (TypeError, ValueError):
        offset = 0
    memories = await store.list_memories(user_id, limit=limit, offset=offset)
    return web.json_response({"memories": [_memory_to_json(m) for m in memories]})


async def get_memory(request: web.Request) -> web.Response:
    memory_id = request.match_info["memory_id"]
    store = request.app["memory_store"]
    memory = await store.get_memory(memory_id)
    if not memory:
        return web.json_response({"error": "Not found"}, status=404)
    return web.json_response(_memory_to_json(memory))


async def create_memory(request: web.Request) -> web.Response:
    try:
        body = await request.json() if request.body_exists else {}
    except Exception:
        body = {}
    if not isinstance(body, dict):
        body = {}
    key = body.get("key")
    content = body.get("content")
    if not isinstance(key, str) or not key.strip():
        return web.json_response({"error": "Missing or invalid 'key'"}, status=400)
    if not isinstance(content, str):
        return web.json_response({"error": "Missing or invalid 'content'"}, status=400)
    store = request.app["memory_store"]
    user_id = request.app["config"].app.default_user_id
    memory = await store.create_memory(user_id, key=key.strip(), content=content.strip())
    return web.json_response(_memory_to_json(memory), status=201)


async def update_memory(request: web.Request) -> web.Response:
    memory_id = request.match_info["memory_id"]
    try:
        body = await request.json() if request.body_exists else {}
    except Exception:
        body = {}
    if not isinstance(body, dict):
        body = {}
    content = body.get("content")
    if not isinstance(content, str):
        return web.json_response({"error": "Missing or invalid 'content'"}, status=400)
    store = request.app["memory_store"]
    updated = await store.update_memory(memory_id, content.strip())
    if not updated:
        return web.json_response({"error": "Not found"}, status=404)
    return web.json_response(_memory_to_json(updated))


async def delete_memory(request: web.Request) -> web.Response:
    memory_id = request.match_info["memory_id"]
    store = request.app["memory_store"]
    ok = await store.delete_memory(memory_id)
    if not ok:
        return web.json_response({"error": "Not found"}, status=404)
    return web.json_response(status=204)


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
    app.router.add_get("/chats/{chat_id}/messages", get_chat_messages)
    app.router.add_get("/chats/{chat_id}", get_chat)
    app.router.add_post("/chats", create_chat)
    app.router.add_patch("/chats/{chat_id}", update_chat)
    app.router.add_delete("/chats/{chat_id}", delete_chat)
    app.router.add_get("/memories", list_memories)
    app.router.add_get("/memories/{memory_id}", get_memory)
    app.router.add_post("/memories", create_memory)
    app.router.add_patch("/memories/{memory_id}", update_memory)
    app.router.add_delete("/memories/{memory_id}", delete_memory)
    app.router.add_get("/models", list_models)
    app.router.add_get("/settings", get_settings)
    app.router.add_patch("/settings", update_settings)
