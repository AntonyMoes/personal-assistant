# Model providers (stub, OpenAI, local, etc.).

from backend.config import ModelConfig, PROVIDER_OPENAI, PROVIDER_STUB
from backend.providers.openai import OpenAIModelProvider
from backend.providers.stub import StubModelProvider


def create_model_provider(model_config: ModelConfig):
    """Create a model provider instance based on config.model.provider."""
    if model_config.provider == PROVIDER_OPENAI:
        return OpenAIModelProvider(
            api_key=model_config.openai_api_key or None,
            default_model=model_config.default_model,
        )
    return StubModelProvider()


__all__ = [
    "OpenAIModelProvider",
    "PROVIDER_OPENAI",
    "PROVIDER_STUB",
    "StubModelProvider",
    "create_model_provider",
]
