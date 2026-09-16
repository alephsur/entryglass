"""Fixtures with no external API credentials or network requirements."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from entryglass.core.config import Settings
from entryglass.main import create_app


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.delenv("NANSEN_API_KEY", raising=False)
    monkeypatch.delenv("ENTRYGLASS_CORS_ORIGINS", raising=False)
    config = Settings(_env_file=None, environment="test")
    with TestClient(create_app(config)) as test_client:
        yield test_client
