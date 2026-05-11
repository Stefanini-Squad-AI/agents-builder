"""Runtime settings, read from env / .env file via pydantic-settings.

Defaults are wired to match the docker-compose.yml in the repo root so the
service runs out-of-the-box on a fresh checkout (`docker compose up -d` plus
`uv run uvicorn app.main:app --reload`).
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


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
    workshop_default_provider: Literal["anthropic", "openai", "ollama"] = "anthropic"
    workshop_default_model: str = "claude-sonnet-4-5"
    workshop_temperature: float = 0.20

    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    ollama_base_url: str = "http://localhost:11434"

    # -------------------------------------------------------------------
    # Storage
    # -------------------------------------------------------------------
    workshop_data_dir: str = "./data"

    # -------------------------------------------------------------------
    # Web client (used to wire CORS in a later step)
    # -------------------------------------------------------------------
    next_public_api_url: str = "http://localhost:8000"

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
