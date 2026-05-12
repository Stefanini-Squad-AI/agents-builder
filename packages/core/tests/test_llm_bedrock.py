"""Tests for BedrockProvider (Step 1.3 — Bedrock option 1).

Unit tests use unittest.mock to patch the boto3 client — no AWS calls.
The live integration test is guarded by WORKSHOP_RUN_BEDROCK=1 and requires:
  - AWS credentials in the environment or ~/.aws/credentials
  - Bedrock model access enabled for anthropic.claude-3-5-sonnet-20241022-v2:0
    in region us-east-2
"""

from __future__ import annotations

import json
import os
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from app.llm import BedrockProvider
from app.llm.base import ChatMessage, ChatPrompt, ProviderNotConfigured
from app.llm.bedrock import _TOOL_NAME, _build_converse_request, _parse_converse_response
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


class SimpleOutput(BaseModel):
    answer: str = "ok"
    score: int = 0


class RequiredOutput(BaseModel):
    title: str
    items: list[str]


def _prompt(schema: type[BaseModel] = SimpleOutput) -> ChatPrompt[Any]:
    return ChatPrompt(
        system="You are a helpful assistant.",
        messages=[ChatMessage(role="user", content="What is 2+2?")],
        response_schema=schema,
    )


def _make_tool_use_response(tool_input: dict[str, Any]) -> dict[str, Any]:
    """Build a minimal Converse API response dict that looks like a tool_use reply."""
    return {
        "stopReason": "tool_use",
        "output": {
            "message": {
                "role": "assistant",
                "content": [
                    {
                        "type": "toolUse",
                        "toolUseId": "tooluse_abc123",
                        "name": _TOOL_NAME,
                        "input": tool_input,
                    }
                ],
            }
        },
        "usage": {"inputTokens": 120, "outputTokens": 45},
    }


def _make_text_response(text: str, stop_reason: str = "max_tokens") -> dict[str, Any]:
    """Build a Converse API response with a text block (non-tool_use stop)."""
    return {
        "stopReason": stop_reason,
        "output": {
            "message": {
                "role": "assistant",
                "content": [{"type": "text", "text": text}],
            }
        },
        "usage": {"inputTokens": 100, "outputTokens": 30},
    }


# ---------------------------------------------------------------------------
# _build_converse_request unit tests
# ---------------------------------------------------------------------------


def test_build_request_model_id() -> None:
    req = _build_converse_request(
        model_id="anthropic.claude-3-5-sonnet-20241022-v2:0",
        prompt=_prompt(),
        temperature=0.2,
        max_tokens=1024,
    )
    assert req["modelId"] == "anthropic.claude-3-5-sonnet-20241022-v2:0"


def test_build_request_system_block() -> None:
    req = _build_converse_request(
        model_id="test-model",
        prompt=_prompt(),
        temperature=0.0,
        max_tokens=512,
    )
    assert req["system"] == [{"text": "You are a helpful assistant."}]


def test_build_request_messages_format() -> None:
    req = _build_converse_request(
        model_id="test-model",
        prompt=_prompt(),
        temperature=0.0,
        max_tokens=512,
    )
    msgs = req["messages"]
    assert len(msgs) == 1
    assert msgs[0]["role"] == "user"
    assert msgs[0]["content"] == [{"text": "What is 2+2?"}]


def test_build_request_tool_config_has_tool() -> None:
    req = _build_converse_request(
        model_id="test-model",
        prompt=_prompt(),
        temperature=0.0,
        max_tokens=512,
    )
    tools = req["toolConfig"]["tools"]
    assert len(tools) == 1
    assert tools[0]["toolSpec"]["name"] == _TOOL_NAME


def test_build_request_tool_choice_forced() -> None:
    req = _build_converse_request(
        model_id="test-model",
        prompt=_prompt(),
        temperature=0.0,
        max_tokens=512,
    )
    assert req["toolConfig"]["toolChoice"] == {"tool": {"name": _TOOL_NAME}}


def test_build_request_inference_config() -> None:
    req = _build_converse_request(
        model_id="test-model",
        prompt=_prompt(),
        temperature=0.7,
        max_tokens=2048,
    )
    assert req["inferenceConfig"]["temperature"] == 0.7
    assert req["inferenceConfig"]["maxTokens"] == 2048


def test_build_request_schema_no_dollar_keys() -> None:
    """$defs / $schema / $id keys must be stripped — Bedrock rejects them."""
    req = _build_converse_request(
        model_id="test-model",
        prompt=_prompt(),
        temperature=0.0,
        max_tokens=512,
    )
    schema = req["toolConfig"]["tools"][0]["toolSpec"]["inputSchema"]["json"]
    for key in schema:
        assert not key.startswith("$"), f"Unexpected $ key in schema: {key}"


# ---------------------------------------------------------------------------
# _parse_converse_response unit tests
# ---------------------------------------------------------------------------


def test_parse_tool_use_returns_parsed() -> None:
    response = _make_tool_use_response({"answer": "four", "score": 4})
    result = _parse_converse_response(response, _prompt(SimpleOutput), "test-model")
    assert isinstance(result.parsed, SimpleOutput)
    assert result.parsed.answer == "four"
    assert result.parsed.score == 4


def test_parse_tool_use_raw_text_is_json() -> None:
    payload = {"answer": "x", "score": 0}
    response = _make_tool_use_response(payload)
    result = _parse_converse_response(response, _prompt(SimpleOutput), "test-model")
    assert json.loads(result.raw_text) == payload


def test_parse_tool_use_populates_tokens() -> None:
    response = _make_tool_use_response({"answer": "ok"})
    result = _parse_converse_response(response, _prompt(SimpleOutput), "test-model")
    assert result.tokens_in == 120
    assert result.tokens_out == 45


def test_parse_tool_use_schema_validation_failure_gives_none_parsed() -> None:
    """If the tool input doesn't match the schema, parsed=None (parse_error path)."""
    response = _make_tool_use_response({"wrong_field": "oops"})
    prompt: ChatPrompt[RequiredOutput] = ChatPrompt(
        system="sys",
        messages=[ChatMessage(role="user", content="hi")],
        response_schema=RequiredOutput,
    )
    result = _parse_converse_response(response, prompt, "test-model")
    assert result.parsed is None
    assert result.raw_text  # raw text still captured


def test_parse_text_fallback_stop_reason_max_tokens() -> None:
    """max_tokens stop → text captured, parsed=None."""
    response = _make_text_response("partial answer", stop_reason="max_tokens")
    result = _parse_converse_response(response, _prompt(), "test-model")
    assert result.parsed is None
    assert result.raw_text == "partial answer"
    assert result.extra["stop_reason"] == "max_tokens"


def test_parse_provider_name_and_model() -> None:
    response = _make_tool_use_response({"answer": "ok"})
    result = _parse_converse_response(response, _prompt(SimpleOutput), "my-model-id")
    assert result.provider_name == "bedrock"
    assert result.model == "my-model-id"


# ---------------------------------------------------------------------------
# BedrockProvider unit tests (boto3 mocked)
# ---------------------------------------------------------------------------


def _make_provider(model_id: str = "test-model") -> BedrockProvider:
    return BedrockProvider(model_id=model_id, region_name="us-east-2")


def test_provider_name_is_bedrock() -> None:
    p = _make_provider()
    assert p.provider_name == "bedrock"


def test_model_name_property() -> None:
    p = _make_provider("anthropic.claude-3-5-sonnet-20241022-v2:0")
    assert p.model_name == "anthropic.claude-3-5-sonnet-20241022-v2:0"


def test_chat_uses_boto3_converse(monkeypatch: pytest.MonkeyPatch) -> None:
    """chat() calls client.converse() exactly once with our request."""
    mock_client = MagicMock()
    mock_client.converse.return_value = _make_tool_use_response({"answer": "mocked"})

    provider = _make_provider()
    provider._client = mock_client

    result = provider.chat(_prompt(SimpleOutput))

    mock_client.converse.assert_called_once()
    assert isinstance(result.parsed, SimpleOutput)
    assert result.parsed.answer == "mocked"


def test_chat_prompt_temperature_overrides_default() -> None:
    mock_client = MagicMock()
    mock_client.converse.return_value = _make_tool_use_response({"answer": "ok"})

    provider = BedrockProvider(model_id="test", region_name="us-east-2", temperature=0.5)
    provider._client = mock_client

    prompt = ChatPrompt(
        system="sys",
        messages=[ChatMessage(role="user", content="hi")],
        response_schema=SimpleOutput,
        temperature=0.1,  # override
    )
    provider.chat(prompt)

    call_kwargs = mock_client.converse.call_args[1]
    assert call_kwargs["inferenceConfig"]["temperature"] == 0.1


def test_chat_default_temperature_used_when_prompt_has_none() -> None:
    mock_client = MagicMock()
    mock_client.converse.return_value = _make_tool_use_response({"answer": "ok"})

    provider = BedrockProvider(model_id="test", region_name="us-east-2", temperature=0.77)
    provider._client = mock_client
    provider.chat(_prompt())

    call_kwargs = mock_client.converse.call_args[1]
    assert call_kwargs["inferenceConfig"]["temperature"] == 0.77


def test_throttle_retry_succeeds_on_second_attempt() -> None:
    """ThrottlingException on first call → sleep → second call succeeds."""
    import botocore.exceptions  # type: ignore[import-untyped]

    throttle_exc = botocore.exceptions.ClientError(
        {"Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}},
        "Converse",
    )
    mock_client = MagicMock()
    mock_client.converse.side_effect = [
        throttle_exc,
        _make_tool_use_response({"answer": "retry_ok"}),
    ]

    provider = _make_provider()
    provider._client = mock_client

    with patch("app.llm.bedrock.time.sleep") as mock_sleep:
        result = provider.chat(_prompt(SimpleOutput))

    mock_sleep.assert_called_once_with(2.0)
    assert mock_client.converse.call_count == 2
    assert result.parsed is not None
    assert result.parsed.answer == "retry_ok"


def test_throttle_exhausted_returns_none_parsed() -> None:
    """Two consecutive ThrottlingExceptions → parsed=None, no raise."""
    import botocore.exceptions

    throttle_exc = botocore.exceptions.ClientError(
        {"Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}},
        "Converse",
    )
    mock_client = MagicMock()
    mock_client.converse.side_effect = [throttle_exc, throttle_exc]

    provider = _make_provider()
    provider._client = mock_client

    with patch("app.llm.bedrock.time.sleep"):
        result = provider.chat(_prompt(SimpleOutput))

    assert result.parsed is None
    assert "error" in result.extra


def test_non_throttle_exception_returns_none_parsed() -> None:
    """Any non-throttle exception → parsed=None, no raise, error in extra."""
    mock_client = MagicMock()
    mock_client.converse.side_effect = RuntimeError("connection refused")

    provider = _make_provider()
    provider._client = mock_client

    result = provider.chat(_prompt(SimpleOutput))
    assert result.parsed is None
    assert result.extra.get("error") == "connection refused"


def test_check_configured_raises_when_boto3_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """If boto3 cannot be imported, check_configured raises ProviderNotConfigured."""
    import builtins
    real_import = builtins.__import__

    def mock_import(name: str, *args: object, **kwargs: object) -> object:
        if name == "boto3":
            raise ImportError("No module named 'boto3'")
        return real_import(name, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(builtins, "__import__", mock_import)
    provider = _make_provider()
    with pytest.raises(ProviderNotConfigured, match="boto3 is not installed"):
        provider.check_configured()


# ---------------------------------------------------------------------------
# Live integration test — requires real AWS credentials + Bedrock access
# ---------------------------------------------------------------------------


def _skip_if_no_bedrock() -> None:
    if not os.environ.get("WORKSHOP_RUN_BEDROCK"):
        pytest.skip(
            "Set WORKSHOP_RUN_BEDROCK=1 + AWS credentials to run live Bedrock tests. "
            "Requires Bedrock model access for anthropic.claude-3-5-sonnet-20241022-v2:0 "
            "in us-east-2."
        )


@pytest.mark.integration
def test_bedrock_live_structured_output() -> None:
    """Live call: BedrockProvider returns a valid parsed SimpleOutput."""
    _skip_if_no_bedrock()

    provider = BedrockProvider(
        model_id="anthropic.claude-3-5-sonnet-20241022-v2:0",
        region_name="us-east-2",
    )
    prompt: ChatPrompt[SimpleOutput] = ChatPrompt(
        system="You always respond using the structured_output tool.",
        messages=[ChatMessage(role="user", content="Reply with answer='live_ok' and score=42.")],
        response_schema=SimpleOutput,
    )
    result = provider.chat(prompt)

    assert result.provider_name == "bedrock"
    assert result.model == "anthropic.claude-3-5-sonnet-20241022-v2:0"
    assert result.tokens_in is not None and result.tokens_in > 0
    assert result.tokens_out is not None and result.tokens_out > 0
    assert isinstance(result.parsed, SimpleOutput), f"parsed=None, raw={result.raw_text!r}"
