"""LLM provider abstraction layer.

Public re-exports for the rest of the codebase:

    from app.llm import (
        ChatMessage, ChatPrompt, ChatResult,
        LLMProvider, ProviderNotConfigured,
        DummyProvider, LLMService,
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
from app.llm.service import LLMService

__all__ = [
    "ChatMessage",
    "ChatPrompt",
    "ChatResult",
    "DummyProvider",
    "LLMProvider",
    "LLMService",
    "ProviderNotConfigured",
]
