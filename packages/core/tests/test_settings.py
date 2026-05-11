"""Unit tests for app.settings."""

from __future__ import annotations

import pytest
from app.settings import Settings, get_settings


def test_defaults_match_compose() -> None:
    """Default Settings values must work out-of-the-box with the repo's docker-compose."""
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.database_url == ("postgresql+psycopg://workshop:workshop@127.0.0.1:5433/workshop")
    assert s.redis_url == "redis://127.0.0.1:6379/0"
    assert s.workshop_default_provider == "anthropic"
    assert s.workshop_default_model == "claude-sonnet-4-5"
    assert s.workshop_temperature == pytest.approx(0.20)
    assert s.anthropic_api_key is None
    assert s.log_level == "INFO"
    assert s.log_json is False


def test_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """Environment variables override defaults."""
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://x:y@z:1/db")
    monkeypatch.setenv("WORKSHOP_TEMPERATURE", "0.7")
    monkeypatch.setenv("LOG_JSON", "true")

    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.database_url == "postgresql+psycopg://x:y@z:1/db"
    assert s.workshop_temperature == pytest.approx(0.7)
    assert s.log_json is True


def test_get_settings_is_cached() -> None:
    """get_settings() returns the same instance across calls."""
    a = get_settings()
    b = get_settings()
    assert a is b
