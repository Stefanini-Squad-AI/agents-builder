"""Tests for LLMService + pricing module (Step 1.2).

Unit tests (no DB): verify cost calculation and JSON helpers.
Integration tests (real Postgres): verify every run() call writes exactly
one llm_runs row in a terminal state.

Enable integration tests with WORKSHOP_RUN_INTEGRATION=1.
"""

from __future__ import annotations

import os
import uuid
from decimal import Decimal
from typing import Any

import pytest
from app.domain import register_models
from app.enums import LlmRunKind, LlmRunStatus
from app.llm import ChatMessage, ChatPrompt, DummyProvider, LLMService, ProviderNotConfigured
from app.llm.pricing import estimate_cost, known_models
from app.llm.service import _serialise_prompt, _try_parse_json
from pydantic import BaseModel

register_models()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class TinySchema(BaseModel):
    value: str = "ok"


def _prompt(system: str = "Be helpful.") -> ChatPrompt[TinySchema]:
    return ChatPrompt(
        system=system,
        messages=[ChatMessage(role="user", content="Hello.")],
        response_schema=TinySchema,
    )


def _skip_if_no_db() -> None:
    if not os.environ.get("WORKSHOP_RUN_INTEGRATION"):
        pytest.skip("set WORKSHOP_RUN_INTEGRATION=1 to enable; requires docker compose up")


# ---------------------------------------------------------------------------
# Pricing — unit tests (no DB)
# ---------------------------------------------------------------------------


def test_estimate_cost_known_model() -> None:
    cost = estimate_cost("claude-sonnet-4-5", tokens_in=1_000_000, tokens_out=1_000_000)
    assert cost is not None
    # $3/M in + $15/M out = $18 total
    assert cost == Decimal("18.000000")


def test_estimate_cost_zero_tokens() -> None:
    cost = estimate_cost("gpt-4o-mini", tokens_in=0, tokens_out=0)
    assert cost == Decimal("0.000000")


def test_estimate_cost_unknown_model_returns_none() -> None:
    assert estimate_cost("future-model-x99", tokens_in=100, tokens_out=100) is None


def test_estimate_cost_both_none_returns_none() -> None:
    assert estimate_cost("claude-sonnet-4-5", tokens_in=None, tokens_out=None) is None


def test_estimate_cost_partial_none_uses_zero() -> None:
    # tokens_out=None → treat as 0; only input cost
    cost = estimate_cost("claude-sonnet-4-5", tokens_in=1_000_000, tokens_out=None)
    assert cost == Decimal("3.000000")  # $3/M input only


def test_estimate_cost_strips_provider_prefix() -> None:
    # Some wrappers prepend "anthropic/" to the model name.
    cost_plain = estimate_cost("claude-sonnet-4-5", 100, 100)
    cost_prefixed = estimate_cost("anthropic/claude-sonnet-4-5", 100, 100)
    assert cost_plain == cost_prefixed


def test_known_models_non_empty_and_sorted() -> None:
    models = known_models()
    assert len(models) >= 10
    assert models == sorted(models)


# ---------------------------------------------------------------------------
# _serialise_prompt — unit test
# ---------------------------------------------------------------------------


def test_serialise_prompt_includes_system_first() -> None:
    p = _prompt(system="sys-content")
    rows = _serialise_prompt(p)
    assert rows[0] == {"role": "system", "content": "sys-content"}
    assert rows[1]["role"] == "user"


# ---------------------------------------------------------------------------
# _try_parse_json — unit tests
# ---------------------------------------------------------------------------


def test_try_parse_json_valid_dict() -> None:
    result = _try_parse_json('{"a": 1}')
    assert result == {"a": 1}


def test_try_parse_json_valid_list_returns_none() -> None:
    # We only store dicts; list JSON returns None.
    assert _try_parse_json("[1, 2, 3]") is None


def test_try_parse_json_invalid_returns_none() -> None:
    assert _try_parse_json("not json at all") is None


def test_try_parse_json_empty_returns_none() -> None:
    assert _try_parse_json("") is None


# ---------------------------------------------------------------------------
# Integration tests — require live Postgres
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_service_success_writes_one_row() -> None:
    """A successful run() writes exactly one llm_runs row with status=success."""
    _skip_if_no_db()
    from app.db import session_scope
    from app.domain.llm import LlmRun
    from sqlalchemy import select

    provider = DummyProvider(fake_tokens_in=50, fake_tokens_out=20)
    run_id: uuid.UUID | None = None

    with session_scope() as session:
        service = LLMService(provider, session, project_id=None)
        result = service.run(_prompt(), kind=LlmRunKind.OTHER)
        # Flush happened inside run(); get the row while still in transaction.
        rows = session.execute(
            select(LlmRun).order_by(LlmRun.created_at.desc()).limit(1)
        ).scalars().all()
        assert rows, "No llm_runs row written"
        run_id = rows[0].id

    # Re-fetch outside the transaction to confirm commit.
    with session_scope() as session:
        row = session.get(LlmRun, run_id)
        assert row is not None
        assert row.status == LlmRunStatus.SUCCESS.value
        assert row.tokens_in == 50
        assert row.tokens_out == 20
        assert row.response_text is not None
        assert result.parsed is not None


@pytest.mark.integration
def test_service_parse_error_writes_parse_error_status() -> None:
    """When parsed=None the service writes status=parse_error."""
    _skip_if_no_db()
    from app.db import session_scope
    from app.domain.llm import LlmRun
    from sqlalchemy import select

    class StrictSchema(BaseModel):
        required_field: str  # no default — default construction fails

    # Supply a payload missing required_field so model_validate raises.
    provider = DummyProvider(fixed_response={"wrong_key": "oops"})
    run_id: uuid.UUID | None = None

    with session_scope() as session:
        service = LLMService(provider, session)
        prompt: ChatPrompt[StrictSchema] = ChatPrompt(
            system="sys",
            messages=[ChatMessage(role="user", content="hi")],
            response_schema=StrictSchema,
        )
        result = service.run(prompt)
        rows = session.execute(
            select(LlmRun).order_by(LlmRun.created_at.desc()).limit(1)
        ).scalars().all()
        run_id = rows[0].id

    with session_scope() as session:
        row = session.get(LlmRun, run_id)
        assert row is not None
        assert row.status == LlmRunStatus.PARSE_ERROR.value
        assert result.parsed is None


@pytest.mark.integration
def test_service_provider_error_writes_row_and_reraises() -> None:
    """ProviderNotConfigured → writes provider_error row AND re-raises."""
    _skip_if_no_db()
    from app.db import session_scope
    from app.domain.llm import LlmRun
    from sqlalchemy import select

    provider = DummyProvider(configured=False)
    run_id: uuid.UUID | None = None

    with session_scope() as session:
        service = LLMService(provider, session)
        with pytest.raises(ProviderNotConfigured):
            service.run(_prompt())
        rows = session.execute(
            select(LlmRun).order_by(LlmRun.created_at.desc()).limit(1)
        ).scalars().all()
        run_id = rows[0].id

    with session_scope() as session:
        row = session.get(LlmRun, run_id)
        assert row is not None
        assert row.status == LlmRunStatus.PROVIDER_ERROR.value
        assert row.error is not None


@pytest.mark.integration
def test_service_cost_populated_for_known_model() -> None:
    """Cost is computed and stored for known model names."""
    _skip_if_no_db()
    from app.db import session_scope
    from app.domain.llm import LlmRun
    from sqlalchemy import select

    provider = DummyProvider(fake_tokens_in=1_000_000, fake_tokens_out=1_000_000)
    provider.model_name = "claude-sonnet-4-5"

    with session_scope() as session:
        service = LLMService(provider, session)
        service.run(_prompt())
        rows = session.execute(
            select(LlmRun).order_by(LlmRun.created_at.desc()).limit(1)
        ).scalars().all()
        row = rows[0]
        assert row.cost_usd is not None
        # $3/M in + $15/M out = $18
        assert row.cost_usd == Decimal("18.000000")


@pytest.mark.integration
def test_service_cost_none_for_unknown_model() -> None:
    """Cost stays NULL when the model is not in the pricing table."""
    _skip_if_no_db()
    from app.db import session_scope
    from app.domain.llm import LlmRun
    from sqlalchemy import select

    provider = DummyProvider(fake_tokens_in=100, fake_tokens_out=100)
    provider.model_name = "mystery-model-9000"

    with session_scope() as session:
        service = LLMService(provider, session)
        service.run(_prompt())
        rows = session.execute(
            select(LlmRun).order_by(LlmRun.created_at.desc()).limit(1)
        ).scalars().all()
        assert rows[0].cost_usd is None


@pytest.mark.integration
def test_service_prompt_snapshot_stored_in_db() -> None:
    """The prompt system + messages are persisted in prompt_messages_json."""
    _skip_if_no_db()
    from app.db import session_scope
    from app.domain.llm import LlmRun
    from sqlalchemy import select

    provider = DummyProvider()
    p = _prompt(system="Test system content")

    with session_scope() as session:
        service = LLMService(provider, session)
        service.run(p)
        rows = session.execute(
            select(LlmRun).order_by(LlmRun.created_at.desc()).limit(1)
        ).scalars().all()
        row = rows[0]
        snapshot: list[dict[str, Any]] = row.prompt_messages_json
        assert snapshot[0]["role"] == "system"
        assert snapshot[0]["content"] == "Test system content"
        assert any(r["role"] == "user" for r in snapshot)


@pytest.mark.integration
def test_service_kind_stored_correctly() -> None:
    """The kind field is written from the LlmRunKind passed to run()."""
    _skip_if_no_db()
    from app.db import session_scope
    from app.domain.llm import LlmRun
    from sqlalchemy import select

    provider = DummyProvider()

    with session_scope() as session:
        service = LLMService(provider, session)
        service.run(_prompt(), kind=LlmRunKind.PROPOSE_SKILL_SET)
        rows = session.execute(
            select(LlmRun).order_by(LlmRun.created_at.desc()).limit(1)
        ).scalars().all()
        assert rows[0].kind == LlmRunKind.PROPOSE_SKILL_SET.value
