"""Unit tests for the LLM provider abstraction (Step 1.1).

No network calls. All tests use DummyProvider.
"""

from __future__ import annotations

import pytest
from app.llm import (
    ChatMessage,
    ChatPrompt,
    ChatResult,
    DummyProvider,
    LLMProvider,
    ProviderNotConfigured,
)
from app.llm.dummy import _SchemaWithDefaults
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


class SimpleSchema(BaseModel):
    """A schema with no required fields — safe for DummyProvider default construction."""

    label: str = "hello"
    count: int = 0


class RequiredSchema(BaseModel):
    """A schema that REQUIRES a caller-supplied fixed_response."""

    title: str
    items: list[str] = Field(default_factory=list)


def _prompt(schema: type[BaseModel] = SimpleSchema, system: str = "You are a helper.") -> ChatPrompt:  # type: ignore[type-arg]
    return ChatPrompt(
        system=system,
        messages=[ChatMessage(role="user", content="Do something.")],
        response_schema=schema,
    )


# ---------------------------------------------------------------------------
# ChatPrompt validation
# ---------------------------------------------------------------------------


def test_prompt_rejects_empty_messages() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        ChatPrompt(
            system="sys",
            messages=[],
            response_schema=SimpleSchema,
        )


def test_prompt_rejects_no_user_message() -> None:
    with pytest.raises(ValueError, match="at least one 'user'"):
        ChatPrompt(
            system="sys",
            messages=[ChatMessage(role="assistant", content="hi")],
            response_schema=SimpleSchema,
        )


def test_prompt_accepts_valid_messages() -> None:
    p = _prompt()
    assert len(p.messages) == 1
    assert p.messages[0].role == "user"


# ---------------------------------------------------------------------------
# ChatResult helpers
# ---------------------------------------------------------------------------


def test_chat_result_total_tokens_sum() -> None:
    r: ChatResult[SimpleSchema] = ChatResult(
        raw_text="{}",
        parsed=None,
        tokens_in=100,
        tokens_out=50,
    )
    assert r.total_tokens == 150


def test_chat_result_total_tokens_none_when_partial() -> None:
    r: ChatResult[SimpleSchema] = ChatResult(raw_text="{}", parsed=None, tokens_in=100)
    assert r.total_tokens is None


# ---------------------------------------------------------------------------
# DummyProvider — happy path (default construction)
# ---------------------------------------------------------------------------


def test_dummy_returns_chat_result_instance() -> None:
    provider = DummyProvider()
    result = provider.chat(_prompt(SimpleSchema))
    assert isinstance(result, ChatResult)


def test_dummy_parsed_matches_schema() -> None:
    provider = DummyProvider()
    result = provider.chat(_prompt(SimpleSchema))
    assert isinstance(result.parsed, SimpleSchema)


def test_dummy_raw_text_is_valid_json() -> None:
    import json

    provider = DummyProvider()
    result = provider.chat(_prompt(SimpleSchema))
    obj = json.loads(result.raw_text)
    assert isinstance(obj, dict)


def test_dummy_tokens_are_positive() -> None:
    provider = DummyProvider()
    result = provider.chat(_prompt(SimpleSchema))
    assert result.tokens_in is not None and result.tokens_in > 0
    assert result.tokens_out is not None and result.tokens_out > 0


def test_dummy_provider_name_and_model() -> None:
    provider = DummyProvider()
    result = provider.chat(_prompt(SimpleSchema))
    # provider_name uses a DB-valid LlmProvider enum value; model is test-only.
    assert result.provider_name == "anthropic"
    assert result.model == "dummy-1.0"


# ---------------------------------------------------------------------------
# DummyProvider — fixed_response
# ---------------------------------------------------------------------------


def test_dummy_fixed_response_round_trips() -> None:
    payload = {"title": "Test card", "items": ["do A", "do B"]}
    provider = DummyProvider(fixed_response=payload)
    result = provider.chat(_prompt(RequiredSchema))
    assert isinstance(result.parsed, RequiredSchema)
    assert result.parsed.title == "Test card"
    assert result.parsed.items == ["do A", "do B"]


def test_dummy_fixed_response_overrides_defaults() -> None:
    provider = DummyProvider(fixed_response={"label": "overridden", "count": 99})
    result = provider.chat(_prompt(SimpleSchema))
    assert result.parsed is not None
    assert result.parsed.label == "overridden"
    assert result.parsed.count == 99


# ---------------------------------------------------------------------------
# DummyProvider — fake token overrides
# ---------------------------------------------------------------------------


def test_dummy_fake_token_override() -> None:
    provider = DummyProvider(fake_tokens_in=7, fake_tokens_out=3)
    result = provider.chat(_prompt(SimpleSchema))
    assert result.tokens_in == 7
    assert result.tokens_out == 3
    assert result.total_tokens == 10


# ---------------------------------------------------------------------------
# DummyProvider — ProviderNotConfigured
# ---------------------------------------------------------------------------


def test_dummy_unconfigured_raises() -> None:
    provider = DummyProvider(configured=False)
    with pytest.raises(ProviderNotConfigured) as exc_info:
        provider.chat(_prompt(SimpleSchema))
    assert exc_info.value.provider == "dummy"
    assert "configured=False" in str(exc_info.value)


def test_provider_not_configured_str() -> None:
    exc = ProviderNotConfigured("anthropic", "ANTHROPIC_API_KEY is not set")
    assert "anthropic" in str(exc)
    assert "ANTHROPIC_API_KEY" in str(exc)


# ---------------------------------------------------------------------------
# DummyProvider — schema with all-default fields (_SchemaWithDefaults)
# ---------------------------------------------------------------------------


def test_dummy_internal_schema_with_defaults() -> None:
    provider = DummyProvider()
    result = provider.chat(_prompt(_SchemaWithDefaults))
    assert isinstance(result.parsed, _SchemaWithDefaults)
    assert result.parsed.answer == "ok"
    assert result.parsed.score == 0
    assert result.parsed.tags == []


# ---------------------------------------------------------------------------
# LLMProvider is abstract
# ---------------------------------------------------------------------------


def test_llm_provider_is_abstract() -> None:
    """Cannot instantiate LLMProvider directly."""
    with pytest.raises(TypeError):
        LLMProvider()  # type: ignore[abstract]


# ---------------------------------------------------------------------------
# Real-schema smoke: DummyProvider with one of the five LLM I/O schemas
# ---------------------------------------------------------------------------


def test_dummy_with_proposed_skill_set() -> None:
    """DummyProvider can round-trip a fixed ProposedSkillSet payload."""
    from app.enums import SkillKind
    from app.schemas.llm_io import ProposedSkillSet

    payload = {
        "skills": [
            {
                "slug": "proj-analyzer",
                "name": "Project Analyzer",
                "description": "Analyzes project structure",
                "kind": SkillKind.ANALYZER.value,
                "rationale": "Needed for analysis",
                "sibling_refs": [],
            },
            {
                "slug": "proj-context",
                "name": "Project Context",
                "description": "Provides project context",
                "kind": SkillKind.CONTEXT.value,
                "rationale": "Needed for context",
                "sibling_refs": [],
            },
            {
                "slug": "proj-procedure",
                "name": "Project Procedure",
                "description": "Defines procedures",
                "kind": SkillKind.PROCEDURE.value,
                "rationale": "Needed for process",
                "sibling_refs": [],
            },
        ],
        "coverage_notes": "Covers all main areas",
        "gaps": [],
    }
    provider = DummyProvider(fixed_response=payload)
    prompt: ChatPrompt[ProposedSkillSet] = ChatPrompt(
        system="You are a skill proposer.",
        messages=[ChatMessage(role="user", content="Propose skills for a banking project.")],
        response_schema=ProposedSkillSet,
    )
    result = provider.chat(prompt)
    assert isinstance(result.parsed, ProposedSkillSet)
    assert len(result.parsed.skills) == 3
    assert result.parsed.skills[0].slug == "proj-analyzer"
