"""OpenAIProvider — Direct OpenAI API provider.

Uses the `openai` SDK directly for GPT models. Follows the same structured
output pattern as other providers but uses OpenAI's function calling API.

Structured output strategy
──────────────────────────
OpenAI's Chat Completions API supports function calling with JSON Schema
specifications. We define a single function named "structured_output" whose
parameters schema is derived from the `response_schema` Pydantic model, and
force the model to call it via `tool_choice = {"type": "function", "function": {"name": "structured_output"}}`.

The model's function call arguments are then validated with `model_validate()`.

Fallback: if the response doesn't contain a function call (can happen when
`max_tokens` is hit mid-generation or model doesn't support function calling),
we try to parse the text content as JSON, and if that fails, set `parsed = None`.

Retry
─────
One automatic retry on rate limit errors (status 429) with a 2-second sleep.
Any other exception is caught, written as `extra["error"]`, and `parsed = None`
is returned — matching the contract defined in `LLMProvider.chat()`.

Credentials
───────────
Requires `OPENAI_API_KEY` environment variable or explicit `api_key` argument.
Supports Azure OpenAI via `base_url` parameter.
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


class OpenAIProvider(LLMProvider):
    """Direct OpenAI API provider."""

    provider_name = "openai"

    def __init__(
        self,
        model: str = "gpt-4o",
        api_key: str | None = None,
        base_url: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> None:
        """Initialize OpenAI provider.

        Args:
            model: OpenAI model name (e.g. "gpt-4o", "gpt-3.5-turbo")
            api_key: OpenAI API key (optional, falls back to OPENAI_API_KEY env var)
            base_url: Custom base URL for Azure OpenAI or compatible APIs
            max_tokens: Maximum tokens to generate (None uses model default)
            temperature: Sampling temperature (None uses model default)
        """
        self.model_name = model
        self.api_key = api_key
        self.base_url = base_url
        self.max_tokens = max_tokens
        self.default_temperature = temperature

        self._client: Any = None  # Lazy-loaded openai.OpenAI client

    def check_configured(self) -> None:
        """Raise `ProviderNotConfigured` if openai SDK is missing or API key unavailable."""
        try:
            import openai  # noqa: F401
        except ImportError as e:
            raise ProviderNotConfigured("openai", "pip install openai required") from e

        # Check if we can create a client (validates API key)
        try:
            client = self._get_client()
            # API key validation happens on client creation
            if not client.api_key:
                raise ProviderNotConfigured("openai", "OPENAI_API_KEY or api_key argument required")
        except ProviderNotConfigured:
            raise  # Re-raise our own exceptions
        except Exception as e:
            raise ProviderNotConfigured("openai", f"configuration error: {e}") from e

    def chat(self, prompt: ChatPrompt[T]) -> ChatResult[T]:
        self.check_configured()

        # Build the OpenAI chat completions request
        request_data = self._build_chat_request(prompt)

        logger.debug(
            "openai_request_built",
            model=self.model_name,
            messages_count=len(request_data["messages"]),
            tool_count=len(request_data.get("tools", [])),
        )

        try:
            # First attempt
            response = self._call_openai_chat(request_data)
            return self._parse_openai_response(response, prompt.response_schema)

        except Exception as first_exc:
            # Check for rate limit (429) and retry once
            if self._is_rate_limit_error(first_exc):
                logger.info("openai_rate_limit_retry", delay_seconds=2)
                time.sleep(2)
                try:
                    response = self._call_openai_chat(request_data)
                    return self._parse_openai_response(response, prompt.response_schema)
                except Exception as retry_exc:
                    logger.warning("openai_retry_failed", error=str(retry_exc))
                    return ChatResult(
                        parsed=None,
                        raw_text="",
                        tokens_in=None,
                        tokens_out=None,
                        extra={"error": f"Retry failed: {retry_exc}"},
                    )
            else:
                # Non-rate-limit error, return immediately
                logger.warning("openai_error", error=str(first_exc))
                return ChatResult(
                    parsed=None,
                    raw_text="",
                    tokens_in=None,
                    tokens_out=None,
                    extra={"error": str(first_exc)},
                )

    def _build_chat_request(self, prompt: ChatPrompt[T]) -> dict[str, Any]:
        """Build OpenAI Chat Completions request from ChatPrompt."""
        # Convert messages to OpenAI format (system messages are supported)
        messages = []
        for msg in prompt.messages:
            messages.append({
                "role": msg.role,
                "content": msg.content
            })

        # Build function schema from Pydantic model
        function_schema = prompt.response_schema.model_json_schema()

        # Remove $defs and flatten schema - OpenAI expects simpler format
        function_parameters = self._simplify_json_schema(function_schema)

        # Define the structured output function
        tools = [{
            "type": "function",
            "function": {
                "name": "structured_output",
                "description": f"Generate structured output conforming to {prompt.response_schema.__name__} schema",
                "parameters": function_parameters
            }
        }]

        # Build request
        request_data = {
            "model": self.model_name,
            "messages": messages,
            "tools": tools,
            "tool_choice": {"type": "function", "function": {"name": "structured_output"}}
        }

        # Add max_tokens if specified (prompt overrides instance default)
        max_tokens = self.max_tokens
        if max_tokens is not None:
            request_data["max_tokens"] = max_tokens

        # Add temperature if specified (prompt overrides instance default)
        temperature = prompt.temperature
        if temperature is None:
            temperature = self.default_temperature
        if temperature is not None:
            request_data["temperature"] = temperature

        return request_data

    def _call_openai_chat(self, request_data: dict[str, Any]) -> Any:
        """Make the actual API call to OpenAI Chat Completions."""
        client = self._get_client()
        return client.chat.completions.create(**request_data)

    def _parse_openai_response(self, response: Any, response_schema: type[T]) -> ChatResult[T]:
        """Parse OpenAI response into ChatResult."""
        # Extract usage info
        tokens_in = getattr(response.usage, "prompt_tokens", None) if response.usage else None
        tokens_out = getattr(response.usage, "completion_tokens", None) if response.usage else None

        # Get the first choice (OpenAI can return multiple choices)
        if not response.choices:
            return ChatResult(
                parsed=None,
                raw_text="",
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                extra={"error": "No choices in response"}
            )

        choice = response.choices[0]
        finish_reason = choice.finish_reason

        # Check for function call
        if choice.message.tool_calls:
            tool_call = choice.message.tool_calls[0]  # Take first tool call
            if tool_call.function.name == "structured_output":
                try:
                    # Parse the function arguments as JSON
                    function_args = json.loads(tool_call.function.arguments)
                    parsed_obj = response_schema.model_validate(function_args)
                    return ChatResult(
                        parsed=parsed_obj,
                        raw_text=tool_call.function.arguments,
                        tokens_in=tokens_in,
                        tokens_out=tokens_out,
                        extra={"finish_reason": finish_reason}
                    )
                except Exception as parse_error:
                    logger.warning(
                        "openai_parse_error",
                        function_args=tool_call.function.arguments,
                        schema=response_schema.__name__,
                        error=str(parse_error)
                    )
                    return ChatResult(
                        parsed=None,
                        raw_text=tool_call.function.arguments,
                        tokens_in=tokens_in,
                        tokens_out=tokens_out,
                        extra={"parse_error": str(parse_error), "finish_reason": finish_reason}
                    )

        # Fallback: try to parse message content as JSON
        text_content = choice.message.content or ""
        if text_content.strip():
            # Try to parse as JSON
            try:
                json_content = json.loads(text_content.strip())
                parsed_obj = response_schema.model_validate(json_content)
                return ChatResult(
                    parsed=parsed_obj,
                    raw_text=text_content,
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                    extra={"finish_reason": finish_reason, "fallback": "json_content"}
                )
            except Exception:
                # JSON parse failed, return text as-is
                pass

        # Final fallback: return unparsed text
        logger.info(
            "openai_text_fallback",
            finish_reason=finish_reason,
            has_tool_calls=bool(choice.message.tool_calls),
            content_length=len(text_content)
        )
        return ChatResult(
            parsed=None,
            raw_text=text_content,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            extra={"finish_reason": finish_reason, "fallback": "text_content"}
        )

    def _get_client(self) -> Any:
        """Get or create the OpenAI client (lazy loading)."""
        if self._client is None:
            try:
                import openai
            except ImportError as e:
                raise ProviderNotConfigured("openai", "pip install openai required") from e

            kwargs = {}
            if self.api_key is not None:
                kwargs["api_key"] = self.api_key
            if self.base_url is not None:
                kwargs["base_url"] = self.base_url

            self._client = openai.OpenAI(**kwargs)
        return self._client

    def _simplify_json_schema(self, schema: dict[str, Any]) -> dict[str, Any]:
        """Simplify JSON schema for OpenAI function parameters format.

        OpenAI expects a flatter schema format without $defs references.
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
        # Check for openai.RateLimitError
        exc_name = type(exc).__name__
        if exc_name == "RateLimitError":
            return True

        # Check for status code 429 in the exception message or attributes
        exc_str = str(exc).lower()
        if "rate limit" in exc_str or "429" in exc_str:
            return True

        # Check if exception has a status_code attribute
        return bool(hasattr(exc, "status_code") and exc.status_code == 429)
