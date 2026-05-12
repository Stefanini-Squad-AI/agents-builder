"""Provider factory for creating LLM providers based on configuration.

Centralizes the logic for instantiating the correct provider based on the
LlmProvider enum value and settings. Handles graceful fallbacks when providers
are not configured properly.
"""

from __future__ import annotations

import structlog

from app.enums import LlmProvider
from app.llm.anthropic import AnthropicProvider
from app.llm.base import LLMProvider, ProviderNotConfigured
from app.llm.bedrock import BedrockProvider
from app.llm.dummy import DummyProvider
from app.llm.ollama import OllamaProvider
from app.llm.openai import OpenAIProvider
from app.settings import Settings

logger = structlog.get_logger()


def create_provider(
    provider_type: LlmProvider,
    settings: Settings,
    model_override: str | None = None,
    temperature_override: float | None = None,
) -> LLMProvider:
    """Create an LLM provider instance based on the provider type and settings.

    Args:
        provider_type: The type of provider to create
        settings: Application settings containing API keys and configuration
        model_override: Override the default model for this provider
        temperature_override: Override the default temperature

    Returns:
        Configured LLMProvider instance

    Raises:
        ProviderNotConfigured: If the provider cannot be configured properly
        ValueError: If the provider type is not supported
    """
    logger.debug(
        "creating_llm_provider",
        provider=provider_type.value,
        model_override=model_override,
        temperature_override=temperature_override,
    )

    if provider_type == LlmProvider.ANTHROPIC:
        model = model_override or settings.anthropic_model
        return AnthropicProvider(
            model=model,
            api_key=settings.anthropic_api_key,
            temperature=temperature_override or settings.workshop_temperature,
        )

    elif provider_type == LlmProvider.BEDROCK:
        model = model_override or settings.bedrock_model_id
        return BedrockProvider(
            model_id=model,
            region_name=settings.aws_region,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            aws_session_token=settings.aws_session_token,
            aws_profile=settings.aws_profile,
            temperature=temperature_override or settings.workshop_temperature,
        )

    elif provider_type == LlmProvider.OPENAI:
        model = model_override or settings.openai_model
        return OpenAIProvider(
            model=model,
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            temperature=temperature_override or settings.workshop_temperature,
        )

    elif provider_type == LlmProvider.OLLAMA:
        model = model_override or settings.ollama_model
        return OllamaProvider(
            model=model,
            base_url=settings.ollama_base_url,
            temperature=temperature_override or settings.workshop_temperature,
        )

    else:
        msg = f"Unsupported provider type: {provider_type}"
        raise ValueError(msg)


def create_default_provider(settings: Settings) -> LLMProvider:
    """Create the default provider based on settings.

    Falls back to DummyProvider if the configured provider is not available.

    Args:
        settings: Application settings

    Returns:
        Configured LLMProvider instance (may be DummyProvider as fallback)
    """
    try:
        provider = create_provider(settings.workshop_default_provider, settings)
        provider.check_configured()
        return provider
    except (ProviderNotConfigured, ValueError) as e:
        logger.warning(
            "default_provider_unavailable",
            provider=settings.workshop_default_provider.value,
            error=str(e),
            fallback="dummy",
        )
        # Return DummyProvider as fallback
        return DummyProvider()


def list_available_providers(settings: Settings) -> list[LlmProvider]:
    """List all provider types that are currently configured and available.

    Args:
        settings: Application settings

    Returns:
        List of provider types that can be successfully created and configured
    """
    available = []

    for provider_type in LlmProvider:
        try:
            provider = create_provider(provider_type, settings)
            provider.check_configured()
            available.append(provider_type)
        except (ProviderNotConfigured, ValueError):
            # Provider not available, skip it
            pass

    logger.debug("available_providers_detected", providers=[p.value for p in available])
    return available


def get_provider_status(provider_type: LlmProvider, settings: Settings) -> dict[str, str]:
    """Get detailed status information for a specific provider.

    Args:
        provider_type: The provider type to check
        settings: Application settings

    Returns:
        Dictionary with status information (status, message, model)
    """
    try:
        provider = create_provider(provider_type, settings)
        provider.check_configured()
        return {
            "status": "available",
            "message": "Provider configured and ready",
            "model": provider.model_name,
        }
    except ProviderNotConfigured as e:
        return {
            "status": "not_configured",
            "message": str(e),
            "model": "N/A",
        }
    except ValueError as e:
        return {
            "status": "unsupported",
            "message": str(e),
            "model": "N/A",
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Unexpected error: {e}",
            "model": "N/A",
        }
