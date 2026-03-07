"""Tests for REST endpoints: health, chats list/get/create/update."""

import pytest


@pytest.mark.asyncio
async def test_health(client):
    resp = await client.get("/health")
    assert resp.status == 200
    data = await resp.json()
    assert data == {"status": "ok"}


@pytest.mark.asyncio
async def test_list_chats_empty(client):
    resp = await client.get("/chats")
    assert resp.status == 200
    data = await resp.json()
    assert "chats" in data
    assert data["chats"] == []


@pytest.mark.asyncio
async def test_create_chat_default_title(client):
    resp = await client.post("/chats", json={})
    assert resp.status == 201
    data = await resp.json()
    assert "id" in data
    assert data["title"] == "New chat"
    assert data["model"] == "stub"
    assert data["archived"] is False
    assert "created_at" in data
    assert "updated_at" in data


@pytest.mark.asyncio
async def test_create_chat_with_title_and_model(client):
    resp = await client.post(
        "/chats", json={"title": "My Chat", "model": "gpt-4o-mini"}
    )
    assert resp.status == 201
    data = await resp.json()
    assert data["title"] == "My Chat"
    assert data["model"] == "gpt-4o-mini"


@pytest.mark.asyncio
async def test_get_chat_not_found(client):
    resp = await client.get("/chats/nonexistent-id-12345")
    assert resp.status == 404
    data = await resp.json()
    assert "error" in data


@pytest.mark.asyncio
async def test_get_chat_after_create(client):
    create_resp = await client.post("/chats", json={"title": "Get me"})
    assert create_resp.status == 201
    chat_id = (await create_resp.json())["id"]
    resp = await client.get(f"/chats/{chat_id}")
    assert resp.status == 200
    data = await resp.json()
    assert data["id"] == chat_id
    assert data["title"] == "Get me"


@pytest.mark.asyncio
async def test_list_chats_returns_created(client):
    await client.post("/chats", json={"title": "First"})
    await client.post("/chats", json={"title": "Second"})
    resp = await client.get("/chats")
    assert resp.status == 200
    data = await resp.json()
    assert len(data["chats"]) >= 2
    titles = {c["title"] for c in data["chats"]}
    assert "First" in titles
    assert "Second" in titles


@pytest.mark.asyncio
async def test_patch_chat_rename(client):
    create_resp = await client.post("/chats", json={"title": "Original"})
    chat_id = (await create_resp.json())["id"]
    resp = await client.patch(f"/chats/{chat_id}", json={"title": "Renamed"})
    assert resp.status == 200
    data = await resp.json()
    assert data["title"] == "Renamed"


@pytest.mark.asyncio
async def test_patch_chat_not_found(client):
    resp = await client.patch(
        "/chats/nonexistent-id-12345", json={"title": "X"}
    )
    assert resp.status == 404


@pytest.mark.asyncio
async def test_get_chat_messages(client, app):
    create_resp = await client.post("/chats", json={"title": "Chat"})
    chat_id = (await create_resp.json())["id"]
    await app["chat_store"].append_messages(
        chat_id,
        [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}],
    )
    resp = await client.get(f"/chats/{chat_id}/messages")
    assert resp.status == 200
    data = await resp.json()
    assert "messages" in data
    assert len(data["messages"]) == 2
    assert data["messages"][0]["role"] == "user"
    assert data["messages"][0]["content"] == "hi"
    assert data["messages"][1]["role"] == "assistant"
    assert data["messages"][1]["content"] == "hello"


@pytest.mark.asyncio
async def test_get_chat_messages_not_found(client):
    resp = await client.get("/chats/nonexistent-id-12345/messages")
    assert resp.status == 404


# --- Memories ---


@pytest.mark.asyncio
async def test_list_memories_empty(client):
    resp = await client.get("/memories")
    assert resp.status == 200
    data = await resp.json()
    assert "memories" in data
    assert data["memories"] == []


@pytest.mark.asyncio
async def test_create_memory(client):
    resp = await client.post(
        "/memories",
        json={"key": "name", "content": "Alice"},
    )
    assert resp.status == 201
    data = await resp.json()
    assert "id" in data
    assert data["key"] == "name"
    assert data["content"] == "Alice"
    assert "created_at" in data
    assert "updated_at" in data


@pytest.mark.asyncio
async def test_create_memory_missing_key(client):
    resp = await client.post("/memories", json={"content": "only"})
    assert resp.status == 400
    resp2 = await client.post("/memories", json={"key": "", "content": "x"})
    assert resp2.status == 400


@pytest.mark.asyncio
async def test_create_memory_missing_content(client):
    resp = await client.post("/memories", json={"key": "k"})
    assert resp.status == 400


@pytest.mark.asyncio
async def test_get_memory(client):
    create_resp = await client.post(
        "/memories", json={"key": "k", "content": "v"}
    )
    memory_id = (await create_resp.json())["id"]
    resp = await client.get(f"/memories/{memory_id}")
    assert resp.status == 200
    data = await resp.json()
    assert data["id"] == memory_id
    assert data["key"] == "k"
    assert data["content"] == "v"


@pytest.mark.asyncio
async def test_get_memory_not_found(client):
    resp = await client.get("/memories/nonexistent-id-12345")
    assert resp.status == 404


@pytest.mark.asyncio
async def test_list_memories_returns_created(client):
    await client.post("/memories", json={"key": "a", "content": "1"})
    await client.post("/memories", json={"key": "b", "content": "2"})
    resp = await client.get("/memories")
    assert resp.status == 200
    data = await resp.json()
    assert len(data["memories"]) >= 2
    keys = {m["key"] for m in data["memories"]}
    assert "a" in keys
    assert "b" in keys


@pytest.mark.asyncio
async def test_patch_memory(client):
    create_resp = await client.post(
        "/memories", json={"key": "k", "content": "old"}
    )
    memory_id = (await create_resp.json())["id"]
    resp = await client.patch(f"/memories/{memory_id}", json={"content": "new"})
    assert resp.status == 200
    data = await resp.json()
    assert data["content"] == "new"
    get_resp = await client.get(f"/memories/{memory_id}")
    assert (await get_resp.json())["content"] == "new"


@pytest.mark.asyncio
async def test_patch_memory_not_found(client):
    resp = await client.patch(
        "/memories/nonexistent-id-12345", json={"content": "x"}
    )
    assert resp.status == 404


@pytest.mark.asyncio
async def test_delete_memory(client):
    create_resp = await client.post(
        "/memories", json={"key": "to-delete", "content": "x"}
    )
    memory_id = (await create_resp.json())["id"]
    resp = await client.delete(f"/memories/{memory_id}")
    assert resp.status == 204
    get_resp = await client.get(f"/memories/{memory_id}")
    assert get_resp.status == 404


@pytest.mark.asyncio
async def test_delete_memory_not_found(client):
    resp = await client.delete("/memories/nonexistent-id-12345")
    assert resp.status == 404
