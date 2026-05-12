"""LLM provider abstraction layer.

Public re-exports for the rest of the codebase:

    from app.llm import (
        ChatMessage, ChatPrompt, ChatResult,
        LLMProvider, ProviderNotConfigured,
        DummyProvider,
    )
"""

from app.llm.base import (
    ChatMessage,
    ChatPrompt,
    ChatResult,
    LLMProvider,
    ProviderNotConfigured,
)
from app.llm.dummy import DummyProvider

__all__ = [
    "ChatMessage",
    "ChatPrompt",
    "ChatResult",
    "DummyProvider",
    "LLMProvider",
    "ProviderNotConfigured",
]
