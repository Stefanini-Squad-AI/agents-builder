"""DummyProvider — a fully deterministic, no-network LLM provider for tests.

Behaviour:
- Validates the prompt (system non-empty, at least one user message).
- Serialises a *default instance* of `response_schema` to JSON and returns it
  as both `raw_text` and `parsed`.  Because Pydantic models with required fields
  would fail default construction, callers can supply a `fixed_response` mapping
  that is used instead.
- Populates fake token counts (len(system) + sum of message lengths, divided by
  4 to approximate tokens; always > 0).
- Raises `ProviderNotConfigured` if constructed with `configured=False` — lets
  tests verify error-handling paths without touching the network.
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel

from app.llm.base import (
    ChatPrompt,
    ChatResult,
    LLMProvider,
    ProviderNotConfigured,
    T,
)

_SENTINEL: dict[str, Any] = {}


class DummyProvider(LLMProvider):
    """Deterministic stand-in for tests and CI.

    Args:
        fixed_response: Optional dict that will be passed to
            `response_schema.model_validate(fixed_response)` instead of
            constructing a default.  Required when the schema has fields
            without defaults.
        configured:     Set to False to simulate a missing-API-key state.
        fake_tokens_in: Override the simulated prompt-token count.
        fake_tokens_out: Override the simulated completion-token count.
    """

    provider_name = "dummy"
    model_name = "dummy-1.0"

    def __init__(
        self,
        *,
        fixed_response: dict[str, Any] | None = None,
        configured: bool = True,
        fake_tokens_in: int | None = None,
        fake_tokens_out: int | None = None,
    ) -> None:
        self._fixed_response = fixed_response
        self._configured = configured
        self._fake_tokens_in = fake_tokens_in
        self._fake_tokens_out = fake_tokens_out

    def check_configured(self) -> None:
        if not self._configured:
            raise ProviderNotConfigured("dummy", "configured=False was set explicitly")

    def chat(self, prompt: ChatPrompt[T]) -> ChatResult[T]:
        self.check_configured()

        # Build the payload to parse
        if self._fixed_response is not None:
            payload = self._fixed_response
        else:
            # Attempt default construction — works for schemas where all fields
            # have defaults; raises ValidationError otherwise (test misconfiguration).
            payload = prompt.response_schema().model_dump()

        raw_text = json.dumps(payload, ensure_ascii=False)

        parsed: T | None
        try:
            parsed = prompt.response_schema.model_validate(payload)
        except Exception:  # broad catch: providers must never crash callers on parse failure
            parsed = None

        tokens_in = self._fake_tokens_in or max(1, _approx_tokens(prompt.system) + sum(
            _approx_tokens(m.content) for m in prompt.messages
        ))
        tokens_out = self._fake_tokens_out or max(1, _approx_tokens(raw_text))

        return ChatResult(
            raw_text=raw_text,
            parsed=parsed,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            provider_name=self.provider_name,
            model=self.model_name,
        )


def _approx_tokens(text: str) -> int:
    """Very rough token estimate: 1 token ≈ 4 characters."""
    return max(1, len(text) // 4)


class _SchemaWithDefaults(BaseModel):
    """Internal test helper — a minimal schema where every field has a default."""

    answer: str = "ok"
    score: int = 0
    tags: list[str] = []
