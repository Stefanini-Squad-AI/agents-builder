"""LLMService — the single gateway for all LLM calls.

Every prompt in the system goes through `LLMService.run()`. The service:

1. Inserts an `llm_runs` row with status `in_progress` before the call.
2. Calls `provider.chat(prompt)`.
3. Updates the row to `success`, `parse_error`, or `provider_error`.
4. Estimates the cost via `app.llm.pricing`.
5. Returns the `ChatResult[T]` to the caller.

Audit Persistence (P3 fix):
The audit row is written to a DEDICATED session that commits immediately,
independent of the caller's session. This guarantees the audit trail survives
even if the caller's transaction rolls back due to an exception. The caller's
session is still accepted for backward compatibility but is no longer used
for audit writes.

Error handling:
- `ProviderNotConfigured` → written as `provider_error`, then re-raised.
- Any other exception from `provider.chat()` → written as `provider_error`,
  then re-raised. The audit row is committed BEFORE the exception propagates.
- `parsed is None` (provider returned text but schema parse failed) →
  written as `parse_error`. The raw text is preserved and the call returns
  normally with `result.parsed = None`.
"""

from __future__ import annotations

import json
import uuid
from decimal import Decimal
from typing import Any

import structlog

from app.db import session_scope
from app.domain.llm import LlmRun
from app.enums import LlmRunKind, LlmRunStatus
from app.llm.base import ChatPrompt, ChatResult, LLMProvider, ProviderNotConfigured, T
from app.llm.pricing import estimate_cost

log = structlog.get_logger(__name__)

# Token budget — using 200k context window models (Claude Sonnet, etc.)
# We estimate ~4 chars per token as a rough heuristic.
_TOKEN_BUDGET = 200_000
_CHARS_PER_TOKEN_ESTIMATE = 4


class LLMService:
    """Wraps a provider and writes every call to the `llm_runs` audit table.

    The audit row is written via a dedicated session that commits immediately,
    ensuring the audit trail survives even if the caller's transaction rolls back.

    Args:
        provider:   Any `LLMProvider` implementation.
        session:    SQLAlchemy `Session` owned by the caller. Kept for backward
                    compatibility but no longer used for audit writes.
        project_id: UUID of the project this call belongs to (may be None for
                    calls not associated with a specific project, e.g. initial
                    setup prompts).
    """

    def __init__(
        self,
        provider: LLMProvider,
        session: Any,  # sqlalchemy.orm.Session — kept for API compatibility
        *,
        project_id: uuid.UUID | None = None,
    ) -> None:
        self._provider = provider
        self._session = session  # kept for backward compat, not used for audit
        self._project_id = project_id

    def run(
        self,
        prompt: ChatPrompt[T],
        *,
        kind: LlmRunKind = LlmRunKind.OTHER,
    ) -> ChatResult[T]:
        """Execute `prompt` and write an audit row.

        Args:
            prompt: The full prompt (system + messages + schema).
            kind:   Which of the five prompt types this is (for audit display).

        Returns:
            The `ChatResult[T]` from the provider. `result.parsed` may be None
            if the provider returned text that failed schema validation.

        Raises:
            ProviderNotConfigured: If the provider is missing required config.
            Exception:             Any other unhandled provider error.
        """
        prompt_snapshot = _serialise_prompt(prompt)
        
        # Token overflow warning — estimate and log if near/over budget
        estimated_tokens = _estimate_prompt_tokens(prompt_snapshot)
        if estimated_tokens > _TOKEN_BUDGET:
            log.warning(
                "prompt_token_overflow",
                estimated_tokens=estimated_tokens,
                budget=_TOKEN_BUDGET,
                kind=kind.value,
                overflow_pct=round((estimated_tokens / _TOKEN_BUDGET - 1) * 100, 1),
                msg="Prompt exceeds token budget. Consider reducing context or splitting the call.",
            )
        elif estimated_tokens > _TOKEN_BUDGET * 0.9:
            log.info(
                "prompt_token_near_budget",
                estimated_tokens=estimated_tokens,
                budget=_TOKEN_BUDGET,
                kind=kind.value,
                usage_pct=round(estimated_tokens / _TOKEN_BUDGET * 100, 1),
            )

        # Create audit row in DEDICATED session — commits immediately (P3 fix)
        run_id = self._create_audit_row(prompt_snapshot, kind, prompt.enable_reasoning)

        bound_log = log.bind(
            llm_run_id=str(run_id),
            kind=kind.value,
            provider=self._provider.provider_name or "unknown",
            model=self._provider.model_name or "unknown",
        )
        bound_log.info("llm_run_start")

        try:
            result: ChatResult[T] = self._provider.chat(prompt)
        except ProviderNotConfigured as exc:
            self._finalise_audit_row(run_id, LlmRunStatus.PROVIDER_ERROR, error=str(exc))
            bound_log.warning("llm_run_provider_not_configured", error=str(exc))
            raise
        except Exception as exc:
            self._finalise_audit_row(run_id, LlmRunStatus.PROVIDER_ERROR, error=str(exc))
            bound_log.error("llm_run_provider_error", error=str(exc))
            raise

        # Success path
        status = LlmRunStatus.SUCCESS if result.parsed is not None else LlmRunStatus.PARSE_ERROR
        self._finalise_audit_row(run_id, status, result=result)

        bound_log.info(
            "llm_run_done",
            status=status.value,
            tokens_in=result.tokens_in,
            tokens_out=result.tokens_out,
            cost_usd=float(result.tokens_in or 0) * 0.001,  # approx for log
        )

        # Attach the LLM run ID for callers that need to link to the audit log
        result.run_id = run_id
        return result

    def _create_audit_row(
        self,
        prompt_snapshot: list[dict[str, Any]],
        kind: LlmRunKind,
        enable_reasoning: bool,
    ) -> uuid.UUID:
        """Insert audit row in dedicated session — committed immediately."""
        with session_scope() as audit_session:
            run = LlmRun(
                project_id=self._project_id,
                kind=kind.value,
                provider=self._provider.provider_name or "unknown",
                model=self._provider.model_name or "unknown",
                prompt_messages_json=prompt_snapshot,
                status=LlmRunStatus.IN_PROGRESS.value,
                extended_thinking_enabled=enable_reasoning,
            )
            audit_session.add(run)
            audit_session.commit()
            return run.id

    def _finalise_audit_row(
        self,
        run_id: uuid.UUID,
        status: LlmRunStatus,
        *,
        error: str | None = None,
        result: ChatResult[Any] | None = None,
    ) -> None:
        """Update audit row in dedicated session — committed immediately."""
        with session_scope() as audit_session:
            run = audit_session.get(LlmRun, run_id)
            if not run:
                log.error("audit_row_missing", run_id=str(run_id))
                return

            run.status = status.value

            if error:
                run.error = error[:2000]

            if result:
                run.response_text = result.raw_text
                run.response_json = _try_parse_json(result.raw_text)
                run.tokens_in = result.tokens_in
                run.tokens_out = result.tokens_out
                run.cost_usd = _compute_cost(run.model, result)
                run.reasoning_md = result.reasoning_md
                run.reasoning_tokens = result.reasoning_tokens

            audit_session.commit()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _serialise_prompt(prompt: ChatPrompt[Any]) -> list[dict[str, Any]]:
    """Serialise system + messages to the JSONB format stored in DB.

    Format: list of {role, content} dicts, with system as the first entry.
    """
    rows: list[dict[str, Any]] = [{"role": "system", "content": prompt.system}]
    rows.extend({"role": m.role, "content": m.content} for m in prompt.messages)
    return rows


def _compute_cost(model: str, result: ChatResult[Any]) -> Decimal | None:
    return estimate_cost(model, result.tokens_in, result.tokens_out)


def _try_parse_json(text: str) -> dict[str, Any] | None:
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
        return None
    except (json.JSONDecodeError, ValueError):
        return None


def _estimate_prompt_tokens(prompt_snapshot: list[dict[str, Any]]) -> int:
    """Estimate token count from serialized prompt.
    
    Uses a simple heuristic of ~4 characters per token.
    This is a rough estimate — actual tokenization varies by model.
    """
    total_chars = sum(len(str(msg.get("content", ""))) for msg in prompt_snapshot)
    return total_chars // _CHARS_PER_TOKEN_ESTIMATE
