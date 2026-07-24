"""Pytest fixtures for backend tests."""

from pathlib import Path

import pytest
import yaml

from backend.main import create_app

_REPO_ROOT = Path(__file__).resolve().parent.parent
_EXAMPLE_CONFIG = _REPO_ROOT / "config.example.yaml"


@pytest.fixture
def app(tmp_path):
    """App with stub provider; in-memory storage so tests do not touch data/."""
    raw = yaml.safe_load(_EXAMPLE_CONFIG.read_text(encoding="utf-8")) or {}
    raw.setdefault("storage", {})
    raw["storage"]["backend"] = "memory"
    raw["storage"]["base_path"] = str(tmp_path / "data")
    # Keep persona loading from the real prompts/ file (path resolved vs project root).
    config_file = tmp_path / "config.yaml"
    config_file.write_text(yaml.dump(raw), encoding="utf-8")
    return create_app(config_path=config_file)


@pytest.fixture
async def client(aiohttp_client, app):
    """Aiohttp test client for the app."""
    return await aiohttp_client(app)
