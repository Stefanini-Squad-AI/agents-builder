"""AnthropicProvider — Direct Anthropic API provider.

Uses the `anthropic` SDK directly for Claude models. Follows the same structured
output pattern as BedrockProvider but uses Anthropic's tool-use API directly.

Structured output strategy
──────────────────────────
Anthropic's Messages API supports tool use with JSON Schema specifications.
We define a single tool named "structured_output" whose input schema is derived
from the `response_schema` Pydantic model, and force the model to use it via
`tool_choice = {"type": "tool", "name": "structured_output"}`.

The model's tool-use input is then validated with `model_validate()`.

Fallback: if the response doesn't contain a tool-use block (can happen when
`max_tokens` is hit mid-generation or model refuses), we capture the raw text
content instead, set `parsed = None`, and record the stop reason in `extra`.

Retry
─────
One automatic retry on rate limit errors (status 429) with a 2-second sleep.
Any other exception is caught, written as `extra["error"]`, and `parsed = None`
is returned — matching the contract defined in `LLMProvider.chat()`.

Credentials
───────────
Requires `ANTHROPIC_API_KEY` environment variable or explicit `api_key` argument.
The client is created lazily on first call to avoid import-time network activity.
"""

from __future__ import annotations

import json
import time
from typing import Any, TypeVar

import structlog

from app.llm.base import (
    ChatPrompt,
    ChatResult,
    LLMProvider,
    ProviderNotConfigured,
)

T = TypeVar("T")

logger = structlog.get_logger()


class AnthropicProvider(LLMProvider):
    """Direct Anthropic API provider."""

    provider_name = "anthropic"

    def __init__(
        self,
        model: str = "claude-3-5-sonnet-20241022",
        api_key: str | None = None,
        max_tokens: int = 4000,
        temperature: float | None = None,
    ) -> None:
        """Initialize Anthropic provider.

        Args:
            model: Anthropic model name (e.g. "claude-3-5-sonnet-20241022")
            api_key: Anthropic API key (optional, falls back to ANTHROPIC_API_KEY env var)
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (None uses model default)
        """
        self.model_name = model
        self.api_key = api_key
        self.max_tokens = max_tokens
        self.default_temperature = temperature

        self._client: Any = None  # Lazy-loaded anthropic.Anthropic client

    def check_configured(self) -> None:
        """Raise `ProviderNotConfigured` if anthropic SDK is missing or API key unavailable."""
        try:
            import anthropic  # noqa: F401
        except ImportError as e:
            raise ProviderNotConfigured("anthropic", "pip install anthropic required") from e

        # Check if we can create a client (validates API key)
        try:
            client = self._get_client()
            # API key validation happens on client creation
            if not client.api_key:
                raise ProviderNotConfigured("anthropic", "ANTHROPIC_API_KEY or api_key argument required")
        except ProviderNotConfigured:
            raise  # Re-raise our own exceptions
        except Exception as e:
            raise ProviderNotConfigured("anthropic", f"configuration error: {e}") from e

    def chat(self, prompt: ChatPrompt[T]) -> ChatResult[T]:
        self.check_configured()

        # Build the Anthropic messages request
        request_data = self._build_messages_request(prompt)

        logger.debug(
            "anthropic_request_built",
            model=self.model_name,
            messages_count=len(request_data["messages"]),
            tool_count=len(request_data.get("tools", [])),
        )

        try:
            # First attempt
            response = self._call_anthropic_messages(request_data)
            return self._parse_anthropic_response(response, prompt.response_schema)

        except Exception as first_exc:
            # Check for rate limit (429) and retry once
            if self._is_rate_limit_error(first_exc):
                logger.info("anthropic_rate_limit_retry", delay_seconds=2)
                time.sleep(2)
                try:
                    response = self._call_anthropic_messages(request_data)
                    return self._parse_anthropic_response(response, prompt.response_schema)
                except Exception as retry_exc:
                    logger.warning("anthropic_retry_failed", error=str(retry_exc))
                    return ChatResult(
                        parsed=None,
                        raw_text="",
                        tokens_in=None,
                        tokens_out=None,
                        extra={"error": f"Retry failed: {retry_exc}"},
                    )
            else:
                # Non-rate-limit error, return immediately
                logger.warning("anthropic_error", error=str(first_exc))
                return ChatResult(
                    parsed=None,
                    raw_text="",
                    tokens_in=None,
                    tokens_out=None,
                    extra={"error": str(first_exc)},
                )

    def _build_messages_request(self, prompt: ChatPrompt[T]) -> dict[str, Any]:
        """Build Anthropic Messages API request from ChatPrompt."""
        # Convert messages to Anthropic format
        messages = []
        system_content = None

        for msg in prompt.messages:
            if msg.role == "system":
                # Anthropic uses separate system parameter, not system messages
                system_content = msg.content
            else:
                messages.append({
                    "role": msg.role,
                    "content": msg.content
                })

        # Build tool schema from Pydantic model
        tool_schema = prompt.response_schema.model_json_schema()

        # Remove $defs and flatten schema - Anthropic expects simpler format
        tool_input_schema = self._simplify_json_schema(tool_schema)

        # Define the structured output tool
        tools = [{
            "name": "structured_output",
            "description": f"Generate structured output conforming to {prompt.response_schema.__name__} schema",
            "input_schema": tool_input_schema
        }]

        # Build request
        request_data = {
            "model": self.model_name,
            "max_tokens": self.max_tokens,
            "messages": messages,
            "tools": tools,
            "tool_choice": {"type": "tool", "name": "structured_output"}
        }

        # Add system message if present
        if system_content:
            request_data["system"] = system_content

        # Add temperature if specified (prompt overrides instance default)
        temperature = prompt.temperature
        if temperature is None:
            temperature = self.default_temperature
        if temperature is not None:
            request_data["temperature"] = temperature

        return request_data

    def _call_anthropic_messages(self, request_data: dict[str, Any]) -> Any:
        """Make the actual API call to Anthropic Messages."""
        client = self._get_client()
        return client.messages.create(**request_data)

    def _parse_anthropic_response(self, response: Any, response_schema: type[T]) -> ChatResult[T]:
        """Parse Anthropic response into ChatResult."""
        # Extract usage info
        tokens_in = getattr(response.usage, "input_tokens", None)
        tokens_out = getattr(response.usage, "output_tokens", None)

        # Look for tool use in the response
        tool_use_block = None
        text_content = ""

        for content_block in response.content:
            if hasattr(content_block, "type"):
                if content_block.type == "tool_use":
                    tool_use_block = content_block
                elif content_block.type == "text":
                    text_content += content_block.text

        if tool_use_block and tool_use_block.name == "structured_output":
            # Parse structured output
            try:
                parsed_obj = response_schema.model_validate(tool_use_block.input)
                return ChatResult(
                    parsed=parsed_obj,
                    raw_text=json.dumps(tool_use_block.input, indent=2),
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                    extra={"stop_reason": response.stop_reason}
                )
            except Exception as parse_error:
                logger.warning(
                    "anthropic_parse_error",
                    tool_input=tool_use_block.input,
                    schema=response_schema.__name__,
                    error=str(parse_error)
                )
                return ChatResult(
                    parsed=None,
                    raw_text=json.dumps(tool_use_block.input, indent=2),
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                    extra={"parse_error": str(parse_error), "stop_reason": response.stop_reason}
                )
        else:
            # Fallback to text content
            logger.info(
                "anthropic_text_fallback",
                stop_reason=response.stop_reason,
                content_blocks=len(response.content)
            )
            return ChatResult(
                parsed=None,
                raw_text=text_content,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                extra={"stop_reason": response.stop_reason, "fallback": "no_tool_use"}
            )

    def _get_client(self) -> Any:
        """Get or create the Anthropic client (lazy loading)."""
        if self._client is None:
            try:
                import anthropic
            except ImportError as e:
                raise ProviderNotConfigured("anthropic", "pip install anthropic required") from e

            self._client = anthropic.Anthropic(api_key=self.api_key)
        return self._client

    def _simplify_json_schema(self, schema: dict[str, Any]) -> dict[str, Any]:
        """Simplify JSON schema for Anthropic tool input format.

        Anthropic expects a flatter schema format without $defs references.
        """
        # Make a copy to avoid modifying the original
        simplified = dict(schema)

        # Remove $defs and inline any references
        if "$defs" in simplified:
            defs = simplified.pop("$defs")
            simplified = self._inline_refs(simplified, defs)

        # Remove $schema if present
        simplified.pop("$schema", None)

        return simplified

    def _inline_refs(self, obj: Any, defs: dict[str, Any]) -> Any:
        """Recursively inline $ref references."""
        if isinstance(obj, dict):
            if "$ref" in obj:
                # Extract the reference key
                ref_key = obj["$ref"].split("/")[-1]  # Get last part after '/'
                if ref_key in defs:
                    return self._inline_refs(defs[ref_key], defs)
                else:
                    # Return original if ref not found
                    return obj
            else:
                # Recursively process dictionary values
                return {k: self._inline_refs(v, defs) for k, v in obj.items()}
        elif isinstance(obj, list):
            # Recursively process list items
            return [self._inline_refs(item, defs) for item in obj]
        else:
            # Return primitive values as-is
            return obj

    def _is_rate_limit_error(self, exc: Exception) -> bool:
        """Check if the exception indicates a rate limit (429) error."""
        # Check for anthropic.RateLimitError or generic HTTP 429
        exc_name = type(exc).__name__
        if exc_name == "RateLimitError":
            return True

        # Check for status code 429 in the exception message or attributes
        exc_str = str(exc).lower()
        if "rate limit" in exc_str or "429" in exc_str:
            return True

        # Check if exception has a status_code attribute
        return bool(hasattr(exc, "status_code") and exc.status_code == 429)
