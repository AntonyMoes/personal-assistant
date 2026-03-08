"""Load and expose main service configuration from config.yaml and environment."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

# Canonical provider names (used by config and providers; defined here to avoid circular import).
PROVIDER_OPENAI = "openai"
PROVIDER_STUB = "stub"

# Canonical storage backend names (used by config and storage factory).
STORAGE_MEMORY = "memory"
STORAGE_FILE = "file"


@dataclass
class ServerConfig:
    host: str = "127.0.0.1"
    port: int = 8765


@dataclass
class AppConfig:
    default_user_id: str = "default"
    # Optional path to Obsidian vault root (for obsidian tool). Empty = tool disabled.
    obsidian_vault_path: str = ""


@dataclass
class StorageConfig:
    base_path: str = "data"
    chats_dir: str = "chats"
    memories_dir: str = "memories"
    embeddings_dir: str = "embeddings"
    # STORAGE_MEMORY (default) or STORAGE_FILE for ChatStore and MemoryStore
    backend: str = "memory"


@dataclass
class ModelConfig:
    provider: str = PROVIDER_STUB
    default_model: str = PROVIDER_STUB
    openai_api_key: str = ""  # default: use OPENAI_API_KEY env


@dataclass
class PermissionsConfig:
    defaults: dict[str, str] = field(default_factory=dict)


@dataclass
class Config:
    server: ServerConfig = field(default_factory=ServerConfig)
    app: AppConfig = field(default_factory=AppConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    model: ModelConfig = field(default_factory=ModelConfig)
    permissions: PermissionsConfig = field(default_factory=PermissionsConfig)


def _substitute_env(value: Any) -> Any:
    """Replace ${VAR} in strings with os.environ.get(VAR, '')."""
    if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
        var = value[2:-1].strip()
        return os.environ.get(var, "")
    if isinstance(value, dict):
        return {k: _substitute_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_substitute_env(v) for v in value]
    return value


def _dict_to_server(data: dict[str, Any] | None) -> ServerConfig:
    if not data:
        return ServerConfig()
    return ServerConfig(
        host=str(data.get("host", "127.0.0.1")),
        port=int(data.get("port", 8765)),
    )


def _dict_to_app(data: dict[str, Any] | None, base: Path | None = None) -> AppConfig:
    if not data:
        return AppConfig()
    vault = data.get("obsidian_vault_path") or ""
    if isinstance(vault, str) and vault.strip() and base is not None:
        p = Path(vault.strip())
        if not p.is_absolute():
            p = (base / p).resolve()
        vault = str(p)
    return AppConfig(
        default_user_id=str(data.get("default_user_id", "default")),
        obsidian_vault_path=vault if isinstance(vault, str) else "",
    )


def _dict_to_storage(data: dict[str, Any] | None, base: Path) -> StorageConfig:
    if not data:
        return StorageConfig()
    base_path = Path(data.get("base_path", "data"))
    if not base_path.is_absolute():
        base_path = base / base_path
    base_path = base_path.resolve()
    chats = data.get("chats_dir", "chats")
    memories = data.get("memories_dir", "memories")
    embeddings = data.get("embeddings_dir", "embeddings")
    backend = str(data.get("backend", STORAGE_MEMORY)).lower().strip() or STORAGE_MEMORY
    return StorageConfig(
        base_path=str(base_path),
        chats_dir=str(base_path / chats) if not Path(chats).is_absolute() else chats,
        memories_dir=str(base_path / memories) if not Path(memories).is_absolute() else memories,
        embeddings_dir=str(base_path / embeddings) if not Path(embeddings).is_absolute() else embeddings,
        backend=backend,
    )


def _dict_to_model(data: dict[str, Any] | None) -> ModelConfig:
    if not data:
        return ModelConfig()
    api_key = str(data.get("openai_api_key") or "")
    if not api_key and os.environ.get("OPENAI_API_KEY"):
        api_key = os.environ.get("OPENAI_API_KEY", "")
    return ModelConfig(
        provider=str(data.get("provider", PROVIDER_STUB)),
        default_model=str(data.get("default_model", PROVIDER_STUB)),
        openai_api_key=api_key,
    )


def _dict_to_permissions(data: dict[str, Any] | None) -> PermissionsConfig:
    if not data:
        return PermissionsConfig()
    defaults = data.get("defaults")
    if isinstance(defaults, dict):
        defaults = {k: str(v) for k, v in defaults.items()}
    else:
        defaults = {}
    return PermissionsConfig(defaults=defaults)


def load_config(config_path: str | Path | None = None) -> Config:
    """
    Load config from YAML file, then apply env substitution and path resolution.
    If config_path is None, looks for config.yaml in project root (parent of backend/).
    """
    base = Path(__file__).resolve().parent.parent
    path = Path(config_path) if config_path else base / "config.yaml"
    raw: dict[str, Any] = {}
    if path.is_file():
        with open(path, encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
    raw = _substitute_env(raw)
    return Config(
        server=_dict_to_server(raw.get("server")),
        app=_dict_to_app(raw.get("app"), base),
        storage=_dict_to_storage(raw.get("storage"), base),
        model=_dict_to_model(raw.get("model")),
        permissions=_dict_to_permissions(raw.get("permissions")),
    )
