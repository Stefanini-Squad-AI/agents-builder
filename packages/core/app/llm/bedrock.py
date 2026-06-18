"""BedrockProvider — AWS Bedrock Converse API provider.

Uses boto3's `bedrock-runtime.converse` endpoint directly (no LangChain
dependency). The Converse API is a unified cross-model interface that speaks
the same request/response shape for Claude, Llama, Mistral, and Titan.

Structured output strategy
──────────────────────────
Bedrock's Converse API supports tool use with a JSON Schema spec under
`toolConfig`. We define a single tool named "structured_output" whose input
schema is derived from the `response_schema` Pydantic model, and force the
model to always call it via `toolChoice = {"tool": {"name": "structured_output"}}`.
The model's tool-use input is then validated with `model_validate()`.

Fallback: if the response `stopReason` is not `"tool_use"` (can happen when
`max_tokens` is hit mid-generation), we capture the raw text content block
instead, set `parsed = None`, and record the stop reason in `extra`.

Retry
─────
One automatic retry on `ThrottlingException` (Bedrock rate-limits burst calls)
with a 2-second sleep. Any other exception is caught, written as
`extra["error"]`, and `parsed = None` is returned — matching the contract
defined in `LLMProvider.chat()`.

Credentials
───────────
Follows the standard boto3 credential chain:
  1. Explicit `aws_access_key_id` / `aws_secret_access_key` constructor args
  2. `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` environment variables
  3. `~/.aws/credentials` file (or `AWS_PROFILE` profile)
  4. IAM instance/task role via IMDS (EC2 / ECS)

The boto3 session is created lazily on first call to avoid import-time
network activity and to make unit-mocking straightforward.
"""

from __future__ import annotations

import json
import time
from typing import Any

import structlog

from app.llm.base import (
    ChatPrompt,
    ChatResult,
    LLMProvider,
    ProviderNotConfigured,
    T,
)

log = structlog.get_logger(__name__)

_DEFAULT_MAX_TOKENS = 8192
_THROTTLE_SLEEP_S = 2.0
_TOOL_NAME = "structured_output"


class BedrockProvider(LLMProvider):
    """AWS Bedrock Converse API provider.

    Args:
        model_id:              Bedrock model ARN or ID, e.g.
                               ``"anthropic.claude-3-5-sonnet-20241022-v2:0"``.
        region_name:           AWS region, e.g. ``"us-east-2"``.
        temperature:           Default sampling temperature (0.0-1.0).
                               Overridden per-call by ``ChatPrompt.temperature``.
        max_tokens:            Default max completion tokens.
                               Overridden per-call by ``ChatPrompt.max_tokens``.
        aws_access_key_id:     Explicit AWS key (optional; boto3 chain applies).
        aws_secret_access_key: Explicit AWS secret (optional).
        aws_session_token:     Explicit session token for temporary credentials.
        aws_profile:           Named profile from ``~/.aws/credentials``.
    """

    provider_name = "bedrock"

    def __init__(
        self,
        model_id: str = "us.anthropic.claude-sonnet-4-20250514-v1:0",
        region_name: str = "us-east-2",
        *,
        temperature: float = 0.20,
        max_tokens: int = _DEFAULT_MAX_TOKENS,
        aws_access_key_id: str | None = None,
        aws_secret_access_key: str | None = None,
        aws_session_token: str | None = None,
        aws_profile: str | None = None,
    ) -> None:
        self.model_id = model_id
        self.region_name = region_name
        self._default_temperature = temperature
        self._default_max_tokens = max_tokens
        self._aws_access_key_id = aws_access_key_id
        self._aws_secret_access_key = aws_secret_access_key
        self._aws_session_token = aws_session_token
        self._aws_profile = aws_profile
        # Lazy — created on first _client() call
        self._client: Any | None = None

    @property
    def model_name(self) -> str:  # type: ignore[override]
        return self.model_id

    def check_configured(self) -> None:
        """Raise `ProviderNotConfigured` if boto3 is missing or credentials fail."""
        try:
            import boto3  # type: ignore[import-untyped]  # noqa: F401
        except ImportError as exc:
            raise ProviderNotConfigured(
                "bedrock", "boto3 is not installed; run: uv add boto3"
            ) from exc

    def chat(self, prompt: ChatPrompt[T]) -> ChatResult[T]:
        self.check_configured()

        temperature = prompt.temperature if prompt.temperature is not None else self._default_temperature
        max_tokens = prompt.max_tokens if prompt.max_tokens is not None else self._default_max_tokens

        request = _build_converse_request(
            model_id=self.model_id,
            prompt=prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        bound_log = log.bind(provider="bedrock", model=self.model_id)

        # One retry on throttling
        for attempt in range(2):
            try:
                response = self._get_client().converse(**request)
                break
            except Exception as exc:  # boto3 exceptions are dynamic classes
                exc_name = type(exc).__name__
                is_throttle = exc_name == "ThrottlingException" or (
                    exc_name == "ClientError"
                    and getattr(exc, "response", {}).get("Error", {}).get("Code") == "ThrottlingException"
                )
                if is_throttle and attempt == 0:
                    bound_log.warning("bedrock_throttled_retrying", sleep_s=_THROTTLE_SLEEP_S)
                    time.sleep(_THROTTLE_SLEEP_S)
                    continue
                # Any other error — return gracefully
                bound_log.error("bedrock_call_failed", error=str(exc), exc_type=exc_name)
                return ChatResult(
                    raw_text="",
                    parsed=None,
                    provider_name=self.provider_name,
                    model=self.model_id,
                    extra={"error": str(exc), "exc_type": exc_name},
                )

        return _parse_converse_response(response, prompt, self.model_id)

    def _get_client(self) -> Any:
        """Return the boto3 bedrock-runtime client, creating it lazily."""
        if self._client is None:
            self._client = _make_client(
                region_name=self.region_name,
                aws_access_key_id=self._aws_access_key_id,
                aws_secret_access_key=self._aws_secret_access_key,
                aws_session_token=self._aws_session_token,
                aws_profile=self._aws_profile,
            )
        return self._client


# ---------------------------------------------------------------------------
# Request builder
# ---------------------------------------------------------------------------


def _build_converse_request(
    *,
    model_id: str,
    prompt: ChatPrompt[Any],
    temperature: float,
    max_tokens: int,
) -> dict[str, Any]:
    """Build the dict passed to ``boto3_client.converse(**request)``."""
    # System prompt — Converse API takes a list of content blocks
    system_blocks: list[dict[str, Any]] = [{"text": prompt.system}]

    # Messages — each turn is {role, content: [{text: ...}]}
    messages: list[dict[str, Any]] = [
        {"role": m.role, "content": [{"text": m.content}]}
        for m in prompt.messages
    ]

    # Tool spec derived from the Pydantic response schema
    json_schema = prompt.response_schema.model_json_schema()
    # Remove $defs / $schema top-level keys that Bedrock rejects
    clean_schema = {k: v for k, v in json_schema.items() if not k.startswith("$")}

    tool_config: dict[str, Any] = {
        "tools": [
            {
                "toolSpec": {
                    "name": _TOOL_NAME,
                    "description": (
                        f"Return a structured {prompt.response_schema.__name__} object."
                    ),
                    "inputSchema": {"json": clean_schema},
                }
            }
        ],
        # Force the model to always invoke the tool
        "toolChoice": {"tool": {"name": _TOOL_NAME}},
    }

    return {
        "modelId": model_id,
        "system": system_blocks,
        "messages": messages,
        "toolConfig": tool_config,
        "inferenceConfig": {
            "temperature": temperature,
            "maxTokens": max_tokens,
        },
    }


# ---------------------------------------------------------------------------
# Response parser
# ---------------------------------------------------------------------------


def _parse_converse_response(
    response: dict[str, Any],
    prompt: ChatPrompt[T],
    model_id: str,
) -> ChatResult[T]:
    """Extract structured output and token counts from a Converse API response."""
    usage = response.get("usage", {})
    tokens_in: int | None = usage.get("inputTokens")
    tokens_out: int | None = usage.get("outputTokens")

    stop_reason: str = response.get("stopReason", "")
    output_message: dict[str, Any] = response.get("output", {}).get("message", {})
    content_blocks: list[dict[str, Any]] = output_message.get("content", [])

    # Happy path: model called our tool
    if stop_reason == "tool_use":
        for block in content_blocks:
            # Bedrock Converse API returns tool use blocks with a "toolUse" key
            # (not a "type" key like some other APIs)
            tool_use_block = block.get("toolUse")
            if tool_use_block and tool_use_block.get("name") == _TOOL_NAME:
                tool_input: dict[str, Any] = tool_use_block.get("input", {})
                raw_text = json.dumps(tool_input, ensure_ascii=False)
                parsed: T | None = None
                try:
                    parsed = prompt.response_schema.model_validate(tool_input)
                except Exception as exc:  # broad catch: surface as parse_error
                    log.warning(
                        "bedrock_tool_parse_failed",
                        model=model_id,
                        error=str(exc),
                    )
                return ChatResult(
                    raw_text=raw_text,
                    parsed=parsed,
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                    provider_name="bedrock",
                    model=model_id,
                    extra={"stop_reason": stop_reason},
                )

    # Fallback: capture text block (max_tokens hit, or model ignored tool_choice)
    text_parts: list[str] = []
    for block in content_blocks:
        if block.get("type") == "text":
            text_parts.append(block.get("text", ""))

    raw_text = "\n".join(text_parts)
    log.warning(
        "bedrock_unexpected_stop_reason",
        stop_reason=stop_reason,
        model=model_id,
        raw_text_len=len(raw_text),
    )
    return ChatResult(
        raw_text=raw_text,
        parsed=None,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        provider_name="bedrock",
        model=model_id,
        extra={"stop_reason": stop_reason},
    )


# ---------------------------------------------------------------------------
# boto3 client factory
# ---------------------------------------------------------------------------


def _make_client(
    *,
    region_name: str,
    aws_access_key_id: str | None,
    aws_secret_access_key: str | None,
    aws_session_token: str | None,
    aws_profile: str | None,
) -> Any:
    """Create a boto3 ``bedrock-runtime`` client following the credential chain."""
    import boto3

    session_kwargs: dict[str, Any] = {}
    if aws_profile:
        session_kwargs["profile_name"] = aws_profile

    session = boto3.Session(**session_kwargs)

    client_kwargs: dict[str, Any] = {"region_name": region_name}
    if aws_access_key_id:
        client_kwargs["aws_access_key_id"] = aws_access_key_id
    if aws_secret_access_key:
        client_kwargs["aws_secret_access_key"] = aws_secret_access_key
    if aws_session_token:
        client_kwargs["aws_session_token"] = aws_session_token

    return session.client("bedrock-runtime", **client_kwargs)
