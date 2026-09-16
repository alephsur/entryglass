"""Prove the provider command is opt-in and credit bounded."""

import json
from types import SimpleNamespace

from entryglass.infrastructure.nansen import cli

BASE_ARGS = [
    "dex-trades",
    "--address",
    "public-wallet",
    "--from",
    "2026-09-01T00:00:00Z",
    "--to",
    "2026-09-02T00:00:00Z",
]


def test_dry_run_does_not_construct_client(monkeypatch, capsys) -> None:
    def fail_client(**_kwargs):
        raise AssertionError("dry-run must not construct an HTTP client")

    monkeypatch.setattr(cli, "NansenClient", fail_client)
    assert cli.main(BASE_ARGS) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["mode"] == "dry_run"
    assert output["documented_credit_cost"] == 1
    assert output["notice"] == "No request was sent and no credits were consumed."
    assert "public-wallet" not in json.dumps(output)


def test_execute_requires_explicit_credit_ceiling(monkeypatch, capsys) -> None:
    def fail_settings():
        raise AssertionError("settings must not load before the budget check")

    monkeypatch.setattr(cli, "Settings", fail_settings)
    args = ["--execute", *BASE_ARGS]
    assert cli.main(args) == 2
    assert "--max-credits must be at least 1" in capsys.readouterr().err


def test_execute_requires_configured_key(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli, "Settings", lambda: SimpleNamespace(nansen_api_key=None))
    args = ["--execute", "--max-credits", "1", *BASE_ARGS]
    assert cli.main(args) == 2
    assert "NANSEN_API_KEY is not configured" in capsys.readouterr().err
