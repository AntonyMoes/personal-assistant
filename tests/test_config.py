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
    assert config.app.system_prompt == ""
    assert config.storage.backend == "file"
    assert config.model.provider == "stub"
    assert config.model.default_model == "stub"
    assert config.context.max_messages == 40


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


def test_load_config_system_prompt(tmp_path):
    """system_prompt_path is resolved and file contents loaded into app.system_prompt."""
    prompt_file = tmp_path / "persona.md"
    prompt_file.write_text("You are a test assistant.\n", encoding="utf-8")
    config_file = tmp_path / "config.yaml"
    # Absolute path so resolution does not depend on project root layout.
    config_file.write_text(f"""
app:
  system_prompt_path: "{prompt_file.as_posix()}"
""")
    config = load_config(config_file)
    assert config.app.system_prompt == "You are a test assistant."
    assert Path(config.app.system_prompt_path) == prompt_file.resolve()


def test_load_config_system_prompt_missing_file(tmp_path):
    """Missing system prompt file yields empty system_prompt (no crash)."""
    config_file = tmp_path / "config.yaml"
    missing = (tmp_path / "missing.md").as_posix()
    config_file.write_text(f"""
app:
  system_prompt_path: "{missing}"
""")
    config = load_config(config_file)
    assert config.app.system_prompt_path.endswith("missing.md")
    assert config.app.system_prompt == ""


def test_load_config_context_section(tmp_path):
    """context.* knobs load into ContextConfig."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
context:
  max_messages: 12
  max_chars: 5000
  summarize_overflow: false
  summary_message_chars: 80
  summary_max_chars: 400
""")
    config = load_config(config_file)
    assert config.context.max_messages == 12
    assert config.context.max_chars == 5000
    assert config.context.summarize_overflow is False
    assert config.context.summary_message_chars == 80
    assert config.context.summary_max_chars == 400


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
