"""Check safe defaults, environment handling, and secret serialization."""

import pytest
from pydantic import ValidationError

from entryglass.core.config import Settings


def test_api_key_is_optional(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NANSEN_API_KEY", raising=False)
    settings = Settings(_env_file=None)
    assert settings.nansen_api_key is None


def test_api_key_is_not_serialized(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NANSEN_API_KEY", "test-placeholder-not-a-real-secret")
    settings = Settings(_env_file=None)
    assert settings.nansen_api_key is not None
    assert "test-placeholder-not-a-real-secret" not in repr(settings)
    assert "nansen_api_key" not in settings.model_dump()
    assert "test-placeholder-not-a-real-secret" not in settings.model_dump_json()


def test_cors_origins_accept_json_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENTRYGLASS_CORS_ORIGINS", '["http://localhost:6000"]')
    settings = Settings(_env_file=None)
    assert settings.cors_origins == ("http://localhost:6000",)


def test_invalid_environment_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, environment="invalid")
