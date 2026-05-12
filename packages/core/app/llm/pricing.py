"""Token-cost estimates for known LLM models.

Rates are expressed in USD per 1 000 000 tokens (as published by each
provider's pricing page). They are hard-coded here so we never make a network
call at runtime. When a model is not in the table the cost is reported as None
(unknown) rather than zero — the distinction matters for audit displays.

Sources (checked 2026-05):
  Anthropic — https://www.anthropic.com/pricing
  OpenAI    — https://openai.com/pricing

Update this table when providers change their prices or when new models are
added in Steps 1.3 / 1.4.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

# (input_per_1m_usd, output_per_1m_usd)
_RATES: dict[str, tuple[Decimal, Decimal]] = {
    # Anthropic Claude 3.x / 4.x
    "claude-3-haiku-20240307": (Decimal("0.25"), Decimal("1.25")),
    "claude-3-sonnet-20240229": (Decimal("3.00"), Decimal("15.00")),
    "claude-3-opus-20240229": (Decimal("15.00"), Decimal("75.00")),
    "claude-3-5-haiku-20241022": (Decimal("0.80"), Decimal("4.00")),
    "claude-3-5-sonnet-20241022": (Decimal("3.00"), Decimal("15.00")),
    "claude-3-5-sonnet-20240620": (Decimal("3.00"), Decimal("15.00")),
    "claude-sonnet-4-5": (Decimal("3.00"), Decimal("15.00")),
    "claude-opus-4-5": (Decimal("15.00"), Decimal("75.00")),
    "claude-haiku-4-5": (Decimal("0.80"), Decimal("4.00")),
    # OpenAI GPT-4o family
    "gpt-4o": (Decimal("2.50"), Decimal("10.00")),
    "gpt-4o-mini": (Decimal("0.15"), Decimal("0.60")),
    "gpt-4-turbo": (Decimal("10.00"), Decimal("30.00")),
    "gpt-4": (Decimal("30.00"), Decimal("60.00")),
    "gpt-3.5-turbo": (Decimal("0.50"), Decimal("1.50")),
    "o1": (Decimal("15.00"), Decimal("60.00")),
    "o1-mini": (Decimal("3.00"), Decimal("12.00")),
    "o3-mini": (Decimal("1.10"), Decimal("4.40")),
}

_ONE_MILLION = Decimal("1000000")
_QUANTIZE = Decimal("0.000001")  # 6 decimal places — matches DB column Numeric(10, 6)


def estimate_cost(
    model: str,
    tokens_in: int | None,
    tokens_out: int | None,
) -> Decimal | None:
    """Return the estimated USD cost for a call, or None if the model is unknown.

    Args:
        model:      Model identifier exactly as returned by the provider.
        tokens_in:  Number of prompt tokens (None → treat as 0 for calculation
                    but returns None when both counts are None).
        tokens_out: Number of completion tokens.

    Returns:
        Rounded `Decimal` cost, or `None` when the model is not in the table
        or both token counts are None.
    """
    if tokens_in is None and tokens_out is None:
        return None

    # Normalize: strip provider prefixes that some wrappers add (e.g. "anthropic/claude-...")
    normalized = model.split("/")[-1].strip()
    rates = _RATES.get(normalized)
    if rates is None:
        return None

    rate_in, rate_out = rates
    in_cost = rate_in * Decimal(tokens_in or 0) / _ONE_MILLION
    out_cost = rate_out * Decimal(tokens_out or 0) / _ONE_MILLION
    return (in_cost + out_cost).quantize(_QUANTIZE, rounding=ROUND_HALF_UP)


def known_models() -> list[str]:
    """Return the list of model identifiers with known pricing."""
    return sorted(_RATES)
