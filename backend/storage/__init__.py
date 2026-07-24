# Storage implementations: in-memory (for testing/development), file-based (persistent), etc.
# Factory functions create the appropriate store from config (like create_model_provider).

from backend.config import PermissionsConfig, StorageConfig, STORAGE_FILE, STORAGE_MEMORY
from backend.interfaces.tools import Capability, Permission
from backend.storage.file import FileSystemChatStore, FileSystemMemoryStore, FileSystemPermissionStore
from backend.storage.memory import InMemoryChatStore, InMemoryEmbeddingStore, InMemoryMemoryStore, InMemoryPermissionStore


def create_chat_store(storage_config: StorageConfig):
    """Create a ChatStore instance based on storage.backend."""
    backend = getattr(storage_config, "backend", STORAGE_MEMORY).lower().strip() or STORAGE_MEMORY
    if backend == STORAGE_FILE:
        return FileSystemChatStore(storage_config.chats_dir)
    return InMemoryChatStore()


def create_memory_store(storage_config: StorageConfig):
    """Create a MemoryStore instance based on storage.backend."""
    backend = getattr(storage_config, "backend", STORAGE_MEMORY).lower().strip() or STORAGE_MEMORY
    if backend == STORAGE_FILE:
        return FileSystemMemoryStore(storage_config.memories_dir)
    return InMemoryMemoryStore()


def create_embedding_store(storage_config: StorageConfig):
    """Create an EmbeddingStore.

    Scaffolding for future RAG / semantic memory: always returns an in-memory store
    (ignores storage.backend / embeddings_dir). No tool reads or writes it yet.
    See AGENTS.md and docs/optimizations.md.
    """
    _ = storage_config  # reserved for a future file-backed implementation
    return InMemoryEmbeddingStore()


def _build_permission_defaults(permissions_config: PermissionsConfig) -> dict[Capability, Permission]:
    """Convert PermissionsConfig.defaults (str -> str) into Capability -> Permission."""
    defaults: dict[Capability, Permission] = {}
    for cap_str, perm_str in (permissions_config.defaults or {}).items():
        try:
            cap = Capability(cap_str)
            # Backwards-compat alias: 'ask_once' -> ASK_ONCE_PER_CHAT
            if perm_str == "ask_once":
                perm_str = Permission.ASK_ONCE_PER_CHAT.value
            perm = Permission(perm_str)
        except ValueError:
            continue
        defaults[cap] = perm
    return defaults


def create_permission_store(storage_config: StorageConfig, permissions_config: PermissionsConfig):
    """Create a PermissionStore instance based on storage.backend and config defaults."""
    backend = getattr(storage_config, "backend", STORAGE_MEMORY).lower().strip() or STORAGE_MEMORY
    defaults = _build_permission_defaults(permissions_config)
    if backend == STORAGE_FILE:
        return FileSystemPermissionStore(storage_config.base_path, defaults)
    return InMemoryPermissionStore(defaults)


__all__ = [
    "FileSystemChatStore",
    "FileSystemMemoryStore",
    "FileSystemPermissionStore",
    "InMemoryChatStore",
    "InMemoryEmbeddingStore",
    "InMemoryMemoryStore",
    "InMemoryPermissionStore",
    "create_chat_store",
    "create_memory_store",
    "create_embedding_store",
    "create_permission_store",
]
