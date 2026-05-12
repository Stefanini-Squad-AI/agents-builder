"""LLMService — the single gateway for all LLM calls.

Every prompt in the system goes through `LLMService.run()`. The service:

1. Inserts an `llm_runs` row with status `in_progress` before the call.
2. Calls `provider.chat(prompt)`.
3. Updates the row to `success`, `parse_error`, or `provider_error`.
4. Estimates the cost via `app.llm.pricing`.
5. Returns the `ChatResult[T]` to the caller.

The caller owns the `Session` — `LLMService` does NOT commit. This keeps the
service composable: a CLI command or API handler can wrap multiple service
calls in a single transaction and commit once.

Error handling:
- `ProviderNotConfigured` → written as `provider_error`, then re-raised.
- Any other exception from `provider.chat()` → written as `provider_error`,
  then re-raised. This means the DB row is always in a terminal state when
  the exception propagates.
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

from app.domain.llm import LlmRun
from app.enums import LlmRunKind, LlmRunStatus
from app.llm.base import ChatPrompt, ChatResult, LLMProvider, ProviderNotConfigured, T
from app.llm.pricing import estimate_cost

log = structlog.get_logger(__name__)


class LLMService:
    """Wraps a provider and writes every call to the `llm_runs` audit table.

    Args:
        provider:   Any `LLMProvider` implementation.
        session:    SQLAlchemy `Session` owned by the caller. The service calls
                    `session.add()` and `session.flush()` but never `commit()`.
        project_id: UUID of the project this call belongs to (may be None for
                    calls not associated with a specific project, e.g. initial
                    setup prompts).
    """

    def __init__(
        self,
        provider: LLMProvider,
        session: Any,  # sqlalchemy.orm.Session — typed as Any to avoid heavy import at top level
        *,
        project_id: uuid.UUID | None = None,
    ) -> None:
        self._provider = provider
        self._session = session
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

        run = LlmRun(
            project_id=self._project_id,
            kind=kind.value,
            provider=self._provider.provider_name or "unknown",
            model=self._provider.model_name or "unknown",
            prompt_messages_json=prompt_snapshot,
            status=LlmRunStatus.IN_PROGRESS.value,
            extended_thinking_enabled=prompt.enable_reasoning,
        )
        self._session.add(run)
        self._session.flush()  # assign run.id before the network call

        bound_log = log.bind(
            llm_run_id=str(run.id),
            kind=kind.value,
            provider=run.provider,
            model=run.model,
        )
        bound_log.info("llm_run_start")

        try:
            result: ChatResult[T] = self._provider.chat(prompt)
        except ProviderNotConfigured as exc:
            _finalise_error(run, LlmRunStatus.PROVIDER_ERROR, str(exc))
            self._session.flush()
            bound_log.warning("llm_run_provider_not_configured", error=str(exc))
            raise
        except Exception as exc:
            _finalise_error(run, LlmRunStatus.PROVIDER_ERROR, str(exc))
            self._session.flush()
            bound_log.error("llm_run_provider_error", error=str(exc))
            raise

        status = LlmRunStatus.SUCCESS if result.parsed is not None else LlmRunStatus.PARSE_ERROR

        cost = _compute_cost(run.model, result)

        run.status = status.value
        run.response_text = result.raw_text
        run.response_json = _try_parse_json(result.raw_text)
        run.tokens_in = result.tokens_in
        run.tokens_out = result.tokens_out
        run.cost_usd = cost
        run.reasoning_md = result.reasoning_md
        run.reasoning_tokens = result.reasoning_tokens
        self._session.flush()

        bound_log.info(
            "llm_run_done",
            status=status.value,
            tokens_in=result.tokens_in,
            tokens_out=result.tokens_out,
            cost_usd=float(cost) if cost is not None else None,
        )

        return result


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


def _finalise_error(run: LlmRun, status: LlmRunStatus, error: str) -> None:
    run.status = status.value
    run.error = error[:2000]  # guard against very long tracebacks


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
