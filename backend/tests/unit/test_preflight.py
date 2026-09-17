"""Verify durable M5 preflight execution and failure accounting."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

from entryglass.application.ingestion import RequestBudget
from entryglass.application.preflight import CurrentContextFetch, RunTokenPreflight
from entryglass.application.reviews import ProviderEvidence, ReviewScope
from entryglass.domain.context import ContextCoverage
from entryglass.domain.preflight import CurrentContext, PreflightStatus
from entryglass.domain.reviews import ReviewStatus
from entryglass.domain.trades import QuoteAsset
from entryglass.infrastructure.storage import SqliteIngestionRepository

WALLET = "11111111111111111111111111111111"
TOKEN = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
QUOTE = "So11111111111111111111111111111111111111112"
NOW = datetime(2026, 9, 17, 12, tzinfo=UTC)


class FakeCurrentProvider:
    documented_credit_cost = 1

    def fetch_current_context(
        self, token_address: str, *, max_attempts: int
    ) -> CurrentContextFetch:
        context = CurrentContext(
            token_address=token_address,
            observed_at=NOW,
            timeframe="1d",
            coverage=ContextCoverage.OBSERVED,
            smart_trader_net_flow_usd=None,
            smart_trader_avg_flow_usd=None,
            smart_trader_wallet_count=None,
        )
        return CurrentContextFetch(
            context=context,
            evidence=ProviderEvidence(
                kind="current_context",
                endpoint="/api/v1/tgm/flow-intelligence",
                subject_hash="a" * 64,
                request_fingerprint="b" * 64,
                response_hash="c" * 64,
                requested_from_utc=NOW - timedelta(days=1),
                requested_to_utc=NOW,
                retrieved_at=NOW,
                request_id="request-current",
                warnings=(),
                quoted_credits=1,
                used_credits=1,
                attempt_count=1,
            ),
        )


def test_preflight_is_durable_with_evidence(tmp_path: Path) -> None:
    storage = SqliteIngestionRepository(tmp_path / "preflight.sqlite3")
    scope = ReviewScope(
        wallet_address=WALLET,
        from_utc=datetime(2026, 8, 1, tzinfo=UTC),
        to_utc=datetime(2026, 9, 1, tzinfo=UTC),
        quote_assets=(QuoteAsset(QUOTE, "SOL"),),
        budget=RequestBudget(10, 10),
    )
    review = storage.create_review(scope, now=NOW)
    storage.finish_review(review.review_id, status=ReviewStatus.COMPLETE)
    preflight = storage.create_preflight(review.review_id, TOKEN, "7d", now=NOW)

    result = RunTokenPreflight(provider=FakeCurrentProvider(), repository=storage).execute(
        preflight.preflight_id, TOKEN
    )

    assert result.status is PreflightStatus.COMPLETE
    assert result.context is not None
    assert result.context.coverage is ContextCoverage.OBSERVED
    assert result.requests_attempted == 1
    assert result.credits_used == 1
    evidence = storage.get_preflight_evidence(result.preflight_id)
    assert evidence is not None
    assert evidence.endpoint == "/api/v1/tgm/flow-intelligence"
