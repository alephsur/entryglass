"""Prove the M2 import command remains explicit, private, and budgeted."""

import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

from entryglass.application.ingestion import ImportScope, RequestBudget
from entryglass.domain.trades import QuoteAsset
from entryglass.infrastructure import ingestion_cli
from entryglass.infrastructure.storage import SqliteIngestionRepository

WALLET = "11111111111111111111111111111111"
QUOTE = "So11111111111111111111111111111111111111112"
ARGS = [
    "run",
    "--address",
    WALLET,
    "--from",
    "2026-09-01T00:00:00Z",
    "--to",
    "2026-09-02T00:00:00Z",
    "--quote",
    f"{QUOTE}=SOL",
    "--max-requests",
    "2",
    "--max-credits",
    "2",
]


def test_dry_run_does_not_open_database_or_provider(monkeypatch, capsys) -> None:
    def fail(*_args, **_kwargs):
        raise AssertionError("dry-run must not open storage or provider connections")

    monkeypatch.setattr(ingestion_cli, "SqliteIngestionRepository", fail)
    monkeypatch.setattr(ingestion_cli, "NansenIngestionClient", fail)

    assert ingestion_cli.main(ARGS) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["mode"] == "dry_run"
    assert output["max_credits"] == 2
    assert WALLET not in json.dumps(output)
    assert QUOTE not in json.dumps(output)


def test_execute_without_key_stops_before_storage(monkeypatch, capsys) -> None:
    def fail(*_args, **_kwargs):
        raise AssertionError("missing credentials must stop before opening storage")

    monkeypatch.setattr(
        ingestion_cli,
        "Settings",
        lambda: SimpleNamespace(
            database_path=Path("data/test.sqlite3"),
            nansen_api_key=None,
        ),
    )
    monkeypatch.setattr(ingestion_cli, "SqliteIngestionRepository", fail)
    assert ingestion_cli.main([*ARGS, "--execute"]) == 2
    assert "NANSEN_API_KEY is not configured" in capsys.readouterr().err


def test_status_and_cancel_use_durable_job_state(tmp_path, monkeypatch, capsys) -> None:
    database = tmp_path / "jobs.sqlite3"
    monkeypatch.setattr(
        ingestion_cli,
        "Settings",
        lambda: SimpleNamespace(database_path=database),
    )
    repository = SqliteIngestionRepository(database)
    job = repository.create_job(
        ImportScope(
            wallet_address=WALLET,
            from_utc=datetime(2026, 9, 1, tzinfo=UTC),
            to_utc=datetime(2026, 9, 2, tzinfo=UTC),
            quote_assets=(QuoteAsset(QUOTE, "SOL"),),
            budget=RequestBudget(max_requests=1, max_credits=1),
        ),
        now=datetime(2026, 9, 2, tzinfo=UTC),
    )

    assert ingestion_cli.main(["status", "--job-id", job.job_id]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "running"
    assert ingestion_cli.main(["cancel", "--job-id", job.job_id]) == 0
    assert json.loads(capsys.readouterr().out)["cancellation_requested"] is True
    assert repository.get_job(job.job_id).cancellation_requested is True
