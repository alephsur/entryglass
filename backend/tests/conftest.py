"""Fixtures with no external API credentials or network requirements."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from entryglass.core.config import Settings
from entryglass.main import create_app


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--run-provider-integration",
        action="store_true",
        default=False,
        help="Run explicitly configured provider tests that can consume credits.",
    )


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[TestClient]:
    monkeypatch.delenv("NANSEN_API_KEY", raising=False)
    monkeypatch.delenv("ENTRYGLASS_CORS_ORIGINS", raising=False)
    config = Settings(
        _env_file=None,
        environment="test",
        database_path=tmp_path / "entryglass.sqlite3",
    )
    with TestClient(create_app(config)) as test_client:
        yield test_client
