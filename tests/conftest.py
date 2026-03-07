"""Pytest fixtures for backend tests."""

from pathlib import Path

import pytest

from backend.main import create_app

# Use the real example config in the repo (provider: stub, so no real API calls).
_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.example.yaml"


@pytest.fixture
def app():
    """Application with in-memory store; config from config.example.yaml (stub provider)."""
    return create_app(config_path=_CONFIG_PATH)


@pytest.fixture
async def client(aiohttp_client, app):
    """Aiohttp test client for the app."""
    return await aiohttp_client(app)
