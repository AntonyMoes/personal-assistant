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
    assert data["model"] == "gpt-4o"
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
