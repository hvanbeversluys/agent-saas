"""
LLM Providers - Implementations for various LLM services.
"""
from typing import Optional, Dict
import structlog

from config import settings
from .base import LLMProvider

logger = structlog.get_logger()

# Provider registry
_providers: Dict[str, type] = {}


def register_provider(name: str):
    """Decorator to register a provider class."""
    def decorator(cls):
        _providers[name] = cls
        return cls
    return decorator


def get_provider(name: str, **kwargs) -> Optional[LLMProvider]:
    """
    Get a provider instance by name.
    
    Args:
        name: Provider name (groq, openai, anthropic, google, mistral)
        **kwargs: Provider-specific configuration
        
    Returns:
        LLMProvider instance or None if not available
    """
    if name not in _providers:
        logger.warning(f"Unknown provider: {name}")
        return None
    
    provider_class = _providers[name]
    
    # Get API key from settings
    api_key = kwargs.pop("api_key", None)
    if not api_key:
        key_map = {
            "groq": settings.GROQ_API_KEY if hasattr(settings, "GROQ_API_KEY") else None,
            "openai": settings.OPENAI_API_KEY,
            "anthropic": settings.ANTHROPIC_API_KEY,
            "google": settings.GOOGLE_API_KEY if hasattr(settings, "GOOGLE_API_KEY") else None,
            "mistral": settings.MISTRAL_API_KEY if hasattr(settings, "MISTRAL_API_KEY") else None,
        }
        api_key = key_map.get(name)
    
    if not api_key:
        logger.debug(f"No API key for provider: {name}")
        return None
    
    return provider_class(api_key=api_key, **kwargs)


def list_providers() -> list[str]:
    """List all registered provider names."""
    return list(_providers.keys())


def get_available_providers(**kwargs) -> Dict[str, LLMProvider]:
    """
    Get all providers that have valid API keys configured.
    
    Returns:
        Dictionary of provider_name -> LLMProvider instances
    """
    available = {}
    
    for name in _providers:
        provider = get_provider(name, **kwargs)
        if provider:
            available[name] = provider
            logger.info(f"LLM provider available: {name}")
    
    if not available:
        logger.warning("No LLM providers available! Check API keys in .env")
    
    return available


# Import provider implementations to trigger registration
from .providers_groq import GroqProvider
from .providers_openai import OpenAIProvider
from .providers_anthropic import AnthropicProvider
