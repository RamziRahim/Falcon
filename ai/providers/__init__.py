# ai/providers/__init__.py
from __future__ import annotations
from ai.providers.gemini_provider import GeminiProvider

def get_ai_provider(provider_name: str):
    mapping = {
        "gemini": GeminiProvider,
    }
    provider_class = mapping.get(provider_name.lower())
    if not provider_class:
        raise ValueError(f"Unsupported AI Provider interface: {provider_name}")
    return provider_class()