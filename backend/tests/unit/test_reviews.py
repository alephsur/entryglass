"""Verify M3 temporal separation and durable M4 review state."""

import hashlib
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from entryglass.application.ingestion import RequestBudget, WalletTradePage, WalletTradeQuery
from entryglass.application.reviews import (
    BuildWalletReview,
    ContextFetch,
    PriceCandle,
    PriceFetch,
    ProviderEvidence,
    ReviewScope,
)
from entryglass.domain.context import HistoricalContext, PreEntryWindow
from entryglass.domain.outcomes import OutcomeState
from entryglass.domain.reviews import ReviewStatus
from entryglass.domain.trades import QuoteAsset, SwapLeg, TradeEntry
from entryglass.infrastructure.storage import SqliteIngestionRepository

WALLET = "11111111111111111111111111111111"
QUOTE = "So11111111111111111111111111111111111111112"
TOKEN = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
ENTRY_AT = datetime(2026, 9, 1, 12, tzinfo=UTC)
NOW = datetime(2026, 9, 17, 12, tzinfo=UTC)


class WalletProvider:
    documented_credit_cost = 1

    def fingerprint(self, query: WalletTradeQuery) -> str:
        return hashlib.sha256(f"{query.page}".encode()).hexdigest()

    def fetch_page(self, query: WalletTradeQuery, *, max_attempts: int) -> WalletTradePage:
        leg = SwapLeg(
            transaction_hash="transaction-1",
            occurred_at=ENTRY_AT,
            bought_address=TOKEN,
            bought_amount=Decimal("2"),
            sold_address=QUOTE,
            sold_amount=Decimal("1"),
            trade_value_usd=Decimal("4"),
        )
        return WalletTradePage(
            legs=(leg,),
            request_fingerprint=self.fingerprint(query),
            response_hash="a" * 64,
            retrieved_at=NOW,
            page=1,
            per_page=query.per_page,
            is_last_page=True,
            used_credits=1,
        )


class HistoryProvider:
    context_credit_cost = 5
    price_credit_cost = 1

    def __init__(self, later_price: Decimal) -> None:
        self.later_price = later_price
        self.context_windows: list[PreEntryWindow] = []

    def fetch_context(
        self, entry: TradeEntry, window: PreEntryWindow, *, max_attempts: int
    ) -> ContextFetch:
        self.context_windows.append(window)
        return ContextFetch(
            context=HistoricalContext(
                entry_id=entry.entry_id,
                window=window,
                smart_trader_net_flow_usd=Decimal("-12.5"),
                smart_trader_avg_flow_usd=None,
                smart_trader_wallet_count=2,
            ),
            evidence=evidence("historical_context", window.from_utc, window.to_utc, 5),
        )

    def fetch_prices(
        self,
        entry: TradeEntry,
        *,
        from_utc: datetime,
        to_utc: datetime,
        max_attempts: int,
    ) -> PriceFetch:
        return PriceFetch(
            candles=(
                PriceCandle(
                    interval_start=entry.occurred_at.replace(day=2, hour=12),
                    close=self.later_price,
                ),
                PriceCandle(
                    interval_start=entry.occurred_at.replace(day=8, hour=12),
                    close=self.later_price,
                ),
                # This open candle must never be selected.
                PriceCandle(interval_start=NOW.replace(hour=12), close=Decimal("999")),
            ),
            evidence=evidence("later_price", from_utc, to_utc, 1),
        )


def evidence(kind: str, from_utc: datetime, to_utc: datetime, credits: int) -> ProviderEvidence:
    return ProviderEvidence(
        kind=kind,
        endpoint=f"/{kind}",
        subject_hash="b" * 64,
        request_fingerprint=f"{kind}-fingerprint",
        response_hash="c" * 64,
        requested_from_utc=from_utc,
        requested_to_utc=to_utc,
        retrieved_at=NOW,
        request_id=f"{kind}-request",
        warnings=(),
        quoted_credits=credits,
        used_credits=credits,
        attempt_count=1,
    )


def scope() -> ReviewScope:
    return ReviewScope(
        wallet_address=WALLET,
        from_utc=datetime(2026, 8, 1, tzinfo=UTC),
        to_utc=datetime(2026, 9, 2, tzinfo=UTC),
        quote_assets=(QuoteAsset(QUOTE, "SOL"),),
        budget=RequestBudget(max_requests=10, max_credits=20),
        max_entries=1,
    )


def execute(tmp_path: Path, later_price: Decimal):
    storage = SqliteIngestionRepository(tmp_path / f"{later_price}.sqlite3")
    job = storage.create_review(scope(), now=NOW)
    history = HistoryProvider(later_price)
    result = BuildWalletReview(
        wallet_provider=WalletProvider(),
        history_provider=history,
        ingestion_repository=storage,
        review_repository=storage,
        clock=lambda: NOW,
    ).execute(job.review_id, scope())
    entry = storage.list_review_entries(job.review_id)[0]
    return storage, result, entry, history


def test_post_entry_prices_cannot_change_pre_entry_context(tmp_path: Path) -> None:
    first_storage, first_job, first_entry, first_history = execute(tmp_path, Decimal("3"))
    second_storage, second_job, second_entry, second_history = execute(tmp_path, Decimal("30"))

    first_context = first_storage.get_historical_context(first_job.review_id, first_entry.entry_id)
    second_context = second_storage.get_historical_context(
        second_job.review_id, second_entry.entry_id
    )
    assert first_context == second_context
    assert first_history.context_windows == second_history.context_windows
    assert first_history.context_windows[0].to_utc == datetime(2026, 9, 1, 11, 59, 59, tzinfo=UTC)
    first_outcome = first_storage.list_outcomes(first_job.review_id, first_entry.entry_id)[0]
    second_outcome = second_storage.list_outcomes(second_job.review_id, second_entry.entry_id)[0]
    assert first_outcome.price_change_pct != second_outcome.price_change_pct


def test_review_persists_progress_outcomes_and_evidence(tmp_path: Path) -> None:
    storage, job, entry, _history = execute(tmp_path, Decimal("3"))
    assert job.status is ReviewStatus.COMPLETE
    assert job.entries_total == 1
    assert job.entries_processed == 1
    outcomes = storage.list_outcomes(job.review_id, entry.entry_id)
    assert [item.state for item in outcomes] == [OutcomeState.OBSERVED, OutcomeState.OBSERVED]
    assert outcomes[0].price_change_pct == Decimal("50.0")
    assert len(storage.list_review_evidence(job.review_id, entry.entry_id)) == 2


def test_unfinished_hourly_candle_is_not_a_completed_outcome(tmp_path: Path) -> None:
    observation_clock = datetime(2026, 9, 2, 12, 30, tzinfo=UTC)

    class OpenCandleHistory(HistoryProvider):
        def fetch_prices(
            self,
            entry: TradeEntry,
            *,
            from_utc: datetime,
            to_utc: datetime,
            max_attempts: int,
        ) -> PriceFetch:
            return PriceFetch(
                candles=(PriceCandle(interval_start=from_utc, close=Decimal("3")),),
                evidence=evidence("later_price", from_utc, to_utc, 1),
            )

    storage = SqliteIngestionRepository(tmp_path / "open-candle.sqlite3")
    job = storage.create_review(scope(), now=observation_clock)
    result = BuildWalletReview(
        wallet_provider=WalletProvider(),
        history_provider=OpenCandleHistory(Decimal("3")),
        ingestion_repository=storage,
        review_repository=storage,
        clock=lambda: observation_clock,
    ).execute(job.review_id, scope())
    reviewed_entry = storage.list_review_entries(job.review_id)[0]
    outcomes = storage.list_outcomes(result.review_id, reviewed_entry.entry_id)
    assert [item.state for item in outcomes] == [
        OutcomeState.MISSING_PRICE,
        OutcomeState.PENDING,
    ]
