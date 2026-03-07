"""Tests for backend.config: load_config, env substitution, path resolution."""

import os
from pathlib import Path

import pytest

from backend.config import load_config


def test_load_config_no_file(tmp_path):
    """With no config file, load_config returns defaults."""
    config = load_config(tmp_path / "nonexistent.yaml")
    assert config.server.host == "127.0.0.1"
    assert config.server.port == 8765
    assert config.app.default_user_id == "default"
    assert config.model.provider == "stub"
    assert config.model.default_model == "stub"


def test_load_config_with_file(tmp_path):
    """With a config file, values are loaded and merged with defaults."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
server:
  port: 9000
app:
  default_user_id: me
model:
  default_model: gpt-4o-mini
""")
    config = load_config(config_file)
    assert config.server.host == "127.0.0.1"
    assert config.server.port == 9000
    assert config.app.default_user_id == "me"
    assert config.model.default_model == "gpt-4o-mini"


def test_load_config_env_substitution(tmp_path):
    """${VAR} in config is replaced with os.environ."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
app:
  default_user_id: ${TEST_USER_ID}
""")
    os.environ["TEST_USER_ID"] = "env-user"
    try:
        config = load_config(config_file)
        assert config.app.default_user_id == "env-user"
    finally:
        os.environ.pop("TEST_USER_ID", None)


def test_load_config_env_substitution_missing(tmp_path):
    """${MISSING} becomes empty string."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
app:
  default_user_id: ${MISSING_VAR_XYZ}
""")
    config = load_config(config_file)
    assert config.app.default_user_id == ""


def test_load_config_storage_paths_resolved(tmp_path):
    """Storage paths are resolved relative to project base (backend's parent)."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
storage:
  base_path: data
  chats_dir: chats
  memories_dir: memories
  embeddings_dir: embeddings
""")
    config = load_config(config_file)
    # base is backend/config.py -> parent.parent (project root)
    assert Path(config.storage.base_path).is_absolute()
    assert config.storage.base_path.endswith("data") or "data" in config.storage.chats_dir
    assert "chats" in config.storage.chats_dir
    assert config.storage.chats_dir.startswith(config.storage.base_path)
    assert config.storage.memories_dir.startswith(config.storage.base_path)
    assert config.storage.embeddings_dir.startswith(config.storage.base_path)
