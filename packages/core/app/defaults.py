"""Single source of truth for the default LLM provider/model/temperature.

Any code that needs an "out-of-the-box" default LLM choice (Pydantic schemas,
SQLAlchemy ``server_default``, Settings, the seeder, etc.) must import from
here. To change the default model fleet-wide, edit only this file.

Project records persisted in the database keep their own ``llm_provider`` and
``llm_model`` columns; these constants only seed those columns when the caller
does not specify a value.
"""

from __future__ import annotations

from app.enums import LlmProvider

# Provider that backs the default model. Must be a valid ``LlmProvider`` value.
DEFAULT_LLM_PROVIDER: LlmProvider = LlmProvider.BEDROCK

# Friendly model alias. Translated to a Bedrock-accepted ID in
# ``app.llm.factory._resolve_bedrock_model`` when the provider is Bedrock.
DEFAULT_LLM_MODEL: str = "claude-sonnet-4-5"

# Default sampling temperature for new projects.
DEFAULT_LLM_TEMPERATURE: float = 0.20
