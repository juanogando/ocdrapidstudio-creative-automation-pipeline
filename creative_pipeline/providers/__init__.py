"""Provider factory: pick a generator by name, with an 'auto' mode."""
from __future__ import annotations

import os

from .base import ImageProvider
from .mock_provider import MockProvider
from .openai_provider import OpenAIProvider


def get_provider(name: str = "auto") -> ImageProvider:
    """'auto' uses OpenAI when a key is present, otherwise the offline mock."""
    if name == "auto":
        name = "openai" if os.environ.get("OPENAI_API_KEY") else "mock"
    if name == "openai":
        return OpenAIProvider()
    if name == "mock":
        return MockProvider()
    raise ValueError(f"Unknown provider '{name}' (choose auto, openai or mock)")


__all__ = ["ImageProvider", "MockProvider", "OpenAIProvider", "get_provider"]
