"""Runtime settings, read from env / .env file via pydantic-settings.

Defaults are wired to match the docker-compose.yml in the repo root so the
service runs out-of-the-box on a fresh checkout (`docker compose up -d` plus
`uv run uvicorn app.main:app --reload`).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.defaults import (
    DEFAULT_LLM_MODEL,
    DEFAULT_LLM_PROVIDER,
    DEFAULT_LLM_TEMPERATURE,
)

# Absolute path to packages/core/data — ensures both API and worker use the same location
_PACKAGES_CORE_DIR = Path(__file__).resolve().parent.parent
_DEFAULT_DATA_DIR = str(_PACKAGES_CORE_DIR / "data")


class Settings(BaseSettings):
    """Application configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # -------------------------------------------------------------------
    # Database (Postgres via psycopg, used by SQLAlchemy from Step 0.4 on)
    # -------------------------------------------------------------------
    database_url: str = "postgresql+psycopg://workshop:workshop@127.0.0.1:5433/workshop"

    # -------------------------------------------------------------------
    # Redis (Dramatiq broker + light cache)
    # -------------------------------------------------------------------
    redis_url: str = "redis://127.0.0.1:6379/0"

    # -------------------------------------------------------------------
    # LLM defaults (Anthropic is the only default provider in MVP).
    # OpenAI + Ollama are opt-in: setting their respective key / URL
    # is what enables them at runtime.
    # -------------------------------------------------------------------
    workshop_default_provider: Literal["anthropic", "openai", "ollama", "bedrock"] = DEFAULT_LLM_PROVIDER.value  # type: ignore[assignment]
    workshop_default_model: str = DEFAULT_LLM_MODEL
    workshop_temperature: float = DEFAULT_LLM_TEMPERATURE
    llm_enable_reasoning: bool = False

    # Anthropic settings
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-3-5-sonnet-20241022"

    # OpenAI settings
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o"
    openai_base_url: str | None = None  # For Azure OpenAI or other compatible APIs

    # Ollama settings
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"

    # -------------------------------------------------------------------
    # AWS / Bedrock (all optional — boto3 credential chain applies when absent)
    # -------------------------------------------------------------------
    aws_region: str = "us-east-2"
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    aws_session_token: str | None = None
    aws_profile: str | None = None
    # Default Bedrock model — Claude 3.5 Sonnet v2 in us-east-2
    bedrock_model_id: str = "anthropic.claude-3-5-sonnet-20241022-v2:0"

    # -------------------------------------------------------------------
    # Storage
    # -------------------------------------------------------------------
    workshop_data_dir: str = _DEFAULT_DATA_DIR

    # -------------------------------------------------------------------
    # Web client (used to wire CORS in a later step)
    # -------------------------------------------------------------------
    next_public_api_url: str = "http://localhost:8000"

    # -------------------------------------------------------------------
    # Encryption (for MCP secrets at rest)
    # -------------------------------------------------------------------
    # Base64-encoded 32-byte key for Fernet encryption.
    # Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    # If not set, MCP secrets are stored as plain JSON (not recommended for production).
    workshop_encryption_key: str | None = None

    # -------------------------------------------------------------------
    # Logging
    # -------------------------------------------------------------------
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_json: bool = False  # console renderer in dev; flip to JSON for prod


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a process-wide Settings singleton.

    Cached so the .env file and environment are read only once per process.
    Tests that need fresh values can call `get_settings.cache_clear()`.
    """
    return Settings()
