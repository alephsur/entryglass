"""Explicitly opt-in live verification of the bounded M2 ingestion path."""

import os
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import SecretStr

from entryglass.application.ingestion import ImportScope, ImportWalletEntries, RequestBudget
from entryglass.domain.evidence import CoverageState
from entryglass.domain.trades import QuoteAsset
from entryglass.infrastructure.nansen.ingestion import NansenIngestionClient
from entryglass.infrastructure.storage import SqliteIngestionRepository


def test_live_wallet_ingestion_is_explicit_and_bounded(
    request: pytest.FixtureRequest,
    tmp_path: Path,
) -> None:
    if not request.config.getoption("--run-provider-integration"):
        pytest.skip("requires --run-provider-integration")

    required = {
        "NANSEN_API_KEY": os.getenv("NANSEN_API_KEY"),
        "ENTRYGLASS_INTEGRATION_WALLET": os.getenv("ENTRYGLASS_INTEGRATION_WALLET"),
        "ENTRYGLASS_INTEGRATION_FROM": os.getenv("ENTRYGLASS_INTEGRATION_FROM"),
        "ENTRYGLASS_INTEGRATION_TO": os.getenv("ENTRYGLASS_INTEGRATION_TO"),
        "ENTRYGLASS_INTEGRATION_QUOTE_ADDRESS": os.getenv("ENTRYGLASS_INTEGRATION_QUOTE_ADDRESS"),
        "ENTRYGLASS_INTEGRATION_QUOTE_SYMBOL": os.getenv("ENTRYGLASS_INTEGRATION_QUOTE_SYMBOL"),
        "ENTRYGLASS_INTEGRATION_MAX_REQUESTS": os.getenv("ENTRYGLASS_INTEGRATION_MAX_REQUESTS"),
        "ENTRYGLASS_INTEGRATION_MAX_CREDITS": os.getenv("ENTRYGLASS_INTEGRATION_MAX_CREDITS"),
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        pytest.skip(f"missing explicit integration inputs: {', '.join(missing)}")

    assert all(value is not None for value in required.values())
    scope = ImportScope(
        wallet_address=str(required["ENTRYGLASS_INTEGRATION_WALLET"]),
        from_utc=_timestamp(str(required["ENTRYGLASS_INTEGRATION_FROM"])),
        to_utc=_timestamp(str(required["ENTRYGLASS_INTEGRATION_TO"])),
        quote_assets=(
            QuoteAsset(
                address=str(required["ENTRYGLASS_INTEGRATION_QUOTE_ADDRESS"]),
                symbol=str(required["ENTRYGLASS_INTEGRATION_QUOTE_SYMBOL"]),
            ),
        ),
        budget=RequestBudget(
            max_requests=int(str(required["ENTRYGLASS_INTEGRATION_MAX_REQUESTS"])),
            max_credits=int(str(required["ENTRYGLASS_INTEGRATION_MAX_CREDITS"])),
        ),
        max_entries=1,
        page_size=100,
    )
    base_url = os.getenv("NANSEN_BASE_URL", "https://api.nansen.ai")
    storage = SqliteIngestionRepository(tmp_path / "live.sqlite3")
    with NansenIngestionClient(
        api_key=SecretStr(str(required["NANSEN_API_KEY"])),
        base_url=base_url,
    ) as provider:
        job = ImportWalletEntries(provider=provider, repository=storage).execute(scope)

    assert job.coverage not in {CoverageState.PROVIDER_FAILURE, CoverageState.UNAVAILABLE}
    assert storage.list_evidence(job.job_id)


def _timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Integration timestamps must include a UTC offset or Z.")
    return parsed.astimezone(UTC)
