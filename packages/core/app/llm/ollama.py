"""OllamaProvider — Local Ollama API provider.

Uses HTTP requests directly to communicate with a local Ollama server.
No external Python packages required beyond httpx (already a dependency).

Structured output strategy
──────────────────────────
Ollama supports JSON output mode for compatible models. We try to use
`format: "json"` with a schema-based system prompt for structured output.

For models that support it, we provide the JSON schema in the system prompt
and request JSON format. For older models without JSON mode support, we
fall back to text generation with JSON parsing attempts.

Fallback: if JSON parsing fails or the model doesn't support JSON mode,
we return `parsed = None` with the raw text response.

Retry
─────
One automatic retry on connection errors or 5xx server errors with a 2-second
sleep. Network timeouts and other errors are caught, written as `extra["error"]`,
and `parsed = None` is returned.

Connection
──────────
Connects to Ollama server via HTTP (default: http://localhost:11434).
The server must be running and accessible. Uses httpx for requests.
"""

from __future__ import annotations

import json
import time
from typing import Any, TypeVar

import httpx
import structlog

from app.llm.base import (
    ChatPrompt,
    ChatResult,
    LLMProvider,
    ProviderNotConfigured,
)

T = TypeVar("T")

logger = structlog.get_logger()


class OllamaProvider(LLMProvider):
    """Local Ollama API provider."""

    provider_name = "ollama"

    def __init__(
        self,
        model: str = "llama3.2",
        base_url: str = "http://localhost:11434",
        timeout: float = 60.0,
        temperature: float | None = None,
    ) -> None:
        """Initialize Ollama provider.

        Args:
            model: Ollama model name (e.g. "llama3.2", "codellama")
            base_url: Ollama server URL
            timeout: HTTP request timeout in seconds
            temperature: Sampling temperature (None uses model default)
        """
        self.model_name = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.default_temperature = temperature

    def check_configured(self) -> None:
        """Raise `ProviderNotConfigured` if Ollama server is not reachable."""
        try:
            # Try to connect to Ollama server
            with httpx.Client(timeout=5.0) as client:
                response = client.get(f"{self.base_url}/api/tags")
                response.raise_for_status()

                # Check if our model is available
                models_data = response.json()
                available_models = [m["name"] for m in models_data.get("models", [])]

                # Model names in Ollama can have tags (e.g., "llama3.2:latest")
                # Check for exact match or base name match
                model_found = False
                for available_model in available_models:
                    if (available_model == self.model_name or
                        available_model.split(":")[0] == self.model_name or
                        self.model_name.split(":")[0] == available_model.split(":")[0]):
                        model_found = True
                        break

                if not model_found:
                    logger.warning(
                        "ollama_model_not_found",
                        requested_model=self.model_name,
                        available_models=available_models
                    )
                    # Don't fail here - let the user try anyway

        except Exception as e:
            raise ProviderNotConfigured("ollama", f"server not reachable at {self.base_url}: {e}") from e

    def chat(self, prompt: ChatPrompt[T]) -> ChatResult[T]:
        self.check_configured()

        # Build the Ollama chat request
        request_data = self._build_ollama_request(prompt)

        logger.debug(
            "ollama_request_built",
            model=self.model_name,
            messages_count=len(request_data["messages"]),
            format=request_data.get("format"),
        )

        try:
            # First attempt
            response = self._call_ollama_chat(request_data)
            return self._parse_ollama_response(response, prompt.response_schema)

        except Exception as first_exc:
            # Check for retryable errors and retry once
            if self._is_retryable_error(first_exc):
                logger.info("ollama_retry", delay_seconds=2, error=str(first_exc))
                time.sleep(2)
                try:
                    response = self._call_ollama_chat(request_data)
                    return self._parse_ollama_response(response, prompt.response_schema)
                except Exception as retry_exc:
                    logger.warning("ollama_retry_failed", error=str(retry_exc))
                    return ChatResult(
                        parsed=None,
                        raw_text="",
                        tokens_in=None,
                        tokens_out=None,
                        extra={"error": f"Retry failed: {retry_exc}"},
                    )
            else:
                # Non-retryable error, return immediately
                logger.warning("ollama_error", error=str(first_exc))
                return ChatResult(
                    parsed=None,
                    raw_text="",
                    tokens_in=None,
                    tokens_out=None,
                    extra={"error": str(first_exc)},
                )

    def _build_ollama_request(self, prompt: ChatPrompt[T]) -> dict[str, Any]:
        """Build Ollama chat request from ChatPrompt."""
        # Convert messages to Ollama format
        messages = []
        for msg in prompt.messages:
            messages.append({
                "role": msg.role,
                "content": msg.content
            })

        # Get JSON schema for structured output
        schema = prompt.response_schema.model_json_schema()

        # Add schema information to system message
        schema_prompt = self._build_schema_prompt(schema, prompt.response_schema.__name__)

        # Prepend schema prompt to system message or add new system message
        if messages and messages[0]["role"] == "system":
            messages[0]["content"] = schema_prompt + "\n\n" + messages[0]["content"]
        else:
            messages.insert(0, {
                "role": "system",
                "content": schema_prompt
            })

        # Build request
        request_data = {
            "model": self.model_name,
            "messages": messages,
            "stream": False,
            "format": "json"  # Request JSON output
        }

        # Add temperature if specified (prompt overrides instance default)
        temperature = prompt.temperature
        if temperature is None:
            temperature = self.default_temperature
        if temperature is not None:
            request_data["options"] = {"temperature": temperature}

        return request_data

    def _call_ollama_chat(self, request_data: dict[str, Any]) -> dict[str, Any]:
        """Make the actual API call to Ollama chat endpoint."""
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(
                f"{self.base_url}/api/chat",
                json=request_data
            )
            response.raise_for_status()
            return response.json()

    def _parse_ollama_response(self, response: dict[str, Any], response_schema: type[T]) -> ChatResult[T]:
        """Parse Ollama response into ChatResult."""
        # Ollama doesn't provide detailed token counts by default
        tokens_in = None
        tokens_out = None

        # Extract message content
        message = response.get("message", {})
        content = message.get("content", "")

        if not content.strip():
            return ChatResult(
                parsed=None,
                raw_text="",
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                extra={"error": "Empty response from Ollama"}
            )

        # Try to parse as JSON (since we requested JSON format)
        try:
            json_content = json.loads(content.strip())
            parsed_obj = response_schema.model_validate(json_content)
            return ChatResult(
                parsed=parsed_obj,
                raw_text=content,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                extra={"done": response.get("done", True)}
            )
        except json.JSONDecodeError as json_error:
            logger.info(
                "ollama_json_parse_failed",
                content_preview=content[:100] + "..." if len(content) > 100 else content,
                error=str(json_error)
            )
            # Try to extract JSON from text (sometimes models wrap JSON in markdown)
            extracted_json = self._extract_json_from_text(content)
            if extracted_json:
                try:
                    parsed_obj = response_schema.model_validate(extracted_json)
                    return ChatResult(
                        parsed=parsed_obj,
                        raw_text=content,
                        tokens_in=tokens_in,
                        tokens_out=tokens_out,
                        extra={"done": response.get("done", True), "extraction": "markdown_json"}
                    )
                except Exception as extract_error:
                    logger.warning("ollama_extract_parse_error", error=str(extract_error))

            # Final fallback: return unparsed text
            return ChatResult(
                parsed=None,
                raw_text=content,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                extra={
                    "done": response.get("done", True),
                    "parse_error": str(json_error),
                    "fallback": "text_content"
                }
            )
        except Exception as parse_error:
            logger.warning(
                "ollama_validation_error",
                schema=response_schema.__name__,
                error=str(parse_error)
            )
            return ChatResult(
                parsed=None,
                raw_text=content,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                extra={
                    "done": response.get("done", True),
                    "validation_error": str(parse_error)
                }
            )

    def _build_schema_prompt(self, schema: dict[str, Any], schema_name: str) -> str:
        """Build a system prompt that describes the JSON schema."""
        return f"""You must respond with valid JSON that conforms to the following schema for {schema_name}:

{json.dumps(schema, indent=2)}

Important:
- Your response must be valid JSON only, no other text
- Follow the schema exactly
- Include all required fields
- Use appropriate data types (strings, numbers, booleans, arrays, objects)"""

    def _extract_json_from_text(self, text: str) -> dict[str, Any] | None:
        """Try to extract JSON from text that might contain markdown code blocks."""
        import re

        # Look for JSON in markdown code blocks
        json_patterns = [
            r"```(?:json)?\s*\n(.*?)\n```",  # ```json ... ``` or ``` ... ```
            r"`([^`]+)`",  # Single backticks
            r"\{.*\}",  # Raw JSON objects
        ]

        for pattern in json_patterns:
            matches = re.findall(pattern, text, re.DOTALL)
            for match in matches:
                try:
                    # Clean up the match
                    clean_match = match.strip()
                    if clean_match.startswith("{") or clean_match.startswith("["):
                        return json.loads(clean_match)
                except (json.JSONDecodeError, TypeError):
                    continue

        return None

    def _is_retryable_error(self, exc: Exception) -> bool:
        """Check if the exception is retryable (network/server errors)."""
        # Network errors
        if isinstance(exc, (httpx.ConnectError, httpx.TimeoutException)):
            return True

        # Server errors (5xx)
        if isinstance(exc, httpx.HTTPStatusError):
            return exc.response.status_code >= 500

        # Connection-related errors
        exc_str = str(exc).lower()
        retryable_keywords = ["connection", "timeout", "network", "server error"]
        return any(keyword in exc_str for keyword in retryable_keywords)
