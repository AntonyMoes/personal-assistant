# Storage implementations: in-memory (for testing/development), file-based (persistent), etc.
# Factory functions create the appropriate store from config (like create_model_provider).

from backend.config import StorageConfig, STORAGE_FILE, STORAGE_MEMORY
from backend.storage.file import FileSystemChatStore, FileSystemMemoryStore
from backend.storage.memory import InMemoryChatStore, InMemoryEmbeddingStore, InMemoryMemoryStore


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
    """Create an EmbeddingStore instance. Currently always in-memory."""
    return InMemoryEmbeddingStore()


__all__ = [
    "FileSystemChatStore",
    "FileSystemMemoryStore",
    "InMemoryChatStore",
    "InMemoryEmbeddingStore",
    "InMemoryMemoryStore",
    "create_chat_store",
    "create_memory_store",
    "create_embedding_store",
]
