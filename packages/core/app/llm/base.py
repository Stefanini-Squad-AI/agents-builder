"""LLM provider abstraction — Step 1.1.

Public surface:

    ChatMessage       — a single turn in a conversation
    ChatPrompt        — the full request: system + messages + schema
    ChatResult        — the response: typed output + token counts + reasoning
    LLMProvider       — ABC every concrete provider must implement
    ProviderNotConfigured — raised when a provider is selected but not set up

Design decisions:
- `response_schema` is a Pydantic `BaseModel` *class* (not an instance).
  Providers use it both to build the tool/function spec for structured output
  AND to validate/parse the LLM's reply.
- `ChatResult.parsed` is `T | None`; callers check for None and fall back to
  `raw_text` when structured output parsing fails (graceful degradation).
- `reasoning_md` is populated only when the provider supports extended
  thinking (Anthropic) and the project enables it; otherwise None.
- `LLMProvider` is typed generically over `T` at the call-site, but the
  concrete `chat()` implementations call `response_schema.model_validate(...)`
  themselves and return `ChatResult[Any]`. The generic annotation is for IDE
  help only.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

Role = Literal["system", "user", "assistant"]


@dataclass(frozen=True)
class ChatMessage:
    """A single message in the conversation history."""

    role: Role
    content: str


@dataclass
class ChatPrompt(Generic[T]):
    """Full request payload passed to `LLMProvider.chat()`.

    Attributes:
        system:          System prompt text (the provider places it correctly
                         for each API — Anthropic's top-level `system`, OpenAI
                         `messages[0]{role:system}`, etc.).
        messages:        Ordered list of turns. Must contain at least one user
                         message.
        response_schema: Pydantic model class for structured output.  The
                         provider turns this into a tool/function spec and
                         validates the response.
        temperature:     Sampling temperature override.  None → use the
                         provider's project default.
        max_tokens:      Hard cap on completion tokens.  None → provider
                         default (usually 4096).
        enable_reasoning: Request extended-thinking tokens (Anthropic only).
                         Other providers silently ignore this flag.
    """

    system: str
    messages: list[ChatMessage]
    response_schema: type[T]
    temperature: float | None = None
    max_tokens: int | None = None
    enable_reasoning: bool = False

    def __post_init__(self) -> None:
        if not self.messages:
            raise ValueError("ChatPrompt.messages must not be empty")
        if not any(m.role == "user" for m in self.messages):
            raise ValueError("ChatPrompt.messages must contain at least one 'user' message")


@dataclass
class ChatResult(Generic[T]):
    """Response from `LLMProvider.chat()`.

    Attributes:
        raw_text:         The raw string the provider returned before parsing.
        parsed:           The validated Pydantic instance, or None if parsing
                          failed (providers should log the error; callers decide
                          whether to retry or surface the failure).
        tokens_in:        Prompt token count (None if provider doesn't report).
        tokens_out:       Completion token count (None if provider doesn't report).
        reasoning_md:     Markdown of the model's reasoning trace, populated
                          only when extended thinking was enabled and the
                          provider returned a thinking block.
        reasoning_tokens: Number of tokens consumed by the reasoning block.
        provider_name:    The LlmProvider enum value string (e.g. "anthropic").
        model:            The model identifier actually used for the call.
        extra:            Provider-specific metadata (stop_reason, finish_reason,
                          etc.) for debugging; not used by application logic.
    """

    raw_text: str
    parsed: T | None
    tokens_in: int | None = None
    tokens_out: int | None = None
    reasoning_md: str | None = None
    reasoning_tokens: int | None = None
    provider_name: str = ""
    model: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def total_tokens(self) -> int | None:
        """Sum of in + out, or None if either side is unknown."""
        if self.tokens_in is None or self.tokens_out is None:
            return None
        return self.tokens_in + self.tokens_out


class ProviderNotConfigured(Exception):  # noqa: N818
    """Raised when a provider is selected in settings but not properly configured.

    Typical cause: the API key env-var is absent or empty.
    """

    def __init__(self, provider: str, reason: str) -> None:
        self.provider = provider
        self.reason = reason
        super().__init__(f"Provider '{provider}' is not configured: {reason}")


class LLMProvider(ABC):
    """Abstract base class for all LLM back-ends.

    Concrete subclasses: AnthropicProvider (Step 1.3), OpenAIProvider (Step 1.4),
    OllamaProvider (Step 1.4), DummyProvider (this step, for tests).

    Subclasses MUST implement `chat()`.  They MAY override `provider_name` and
    `model_name` as class-level attributes or instance properties; the defaults
    are empty strings (overridden in every real provider).
    """

    provider_name: str = ""
    model_name: str = ""

    @abstractmethod
    def chat(self, prompt: ChatPrompt[T]) -> ChatResult[T]:
        """Send `prompt` to the LLM and return a `ChatResult`.

        Implementations:
        - MUST populate `raw_text`.
        - MUST attempt to populate `parsed` by calling
          `prompt.response_schema.model_validate(...)` on the parsed JSON.
        - MUST populate `tokens_in` / `tokens_out` when the provider API
          reports them.
        - SHOULD populate `provider_name` and `model` on the result.
        - MUST raise `ProviderNotConfigured` if the provider cannot make calls
          due to missing configuration (key, URL, etc.).
        - SHOULD NOT raise for transient errors; instead return a result with
          `parsed=None` and set `extra["error"]`.
        """

    def check_configured(self) -> None:  # noqa: B027
        """Raise `ProviderNotConfigured` if the provider is not ready to use.

        The default implementation is a no-op. Subclasses with required config
        (e.g. API keys) should override this and call it at the top of `chat()`.
        """
