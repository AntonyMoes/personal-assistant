"""Pytest fixtures for backend tests."""

import pytest

from backend.main import create_app


@pytest.fixture
def app():
    """Application with in-memory store; no config file required."""
    return create_app()


@pytest.fixture
async def client(aiohttp_client, app):
    """Aiohttp test client for the app."""
    return await aiohttp_client(app)
