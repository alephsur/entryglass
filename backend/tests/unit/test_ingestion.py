"""Verify the complete offline M2 ingestion and persistence slice."""

import hashlib
import stat
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from entryglass.application.ingestion import (
    ImportScope,
    ImportWalletEntries,
    RequestBudget,
    TradeProviderFailure,
    WalletTradePage,
    WalletTradeQuery,
)
from entryglass.domain.evidence import CoverageState, ImportStatus
from entryglass.domain.trades import QuoteAsset, SwapLeg
from entryglass.infrastructure.storage import SqliteIngestionRepository

WALLET = "11111111111111111111111111111111"
QUOTE = "So11111111111111111111111111111111111111112"
TOKEN = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
TOKEN_TWO = "metaqbxxUerdq28cj1RbAWkYQm3ybzjb6a8bt518x1s"
NOW = datetime(2026, 9, 2, tzinfo=UTC)


def scope(*, requests: int = 3, credits: int = 3, max_entries: int = 30) -> ImportScope:
    return ImportScope(
        wallet_address=WALLET,
        from_utc=datetime(2026, 9, 1, tzinfo=UTC),
        to_utc=NOW,
        quote_assets=(QuoteAsset(QUOTE, "SOL"),),
        budget=RequestBudget(max_requests=requests, max_credits=credits),
        max_entries=max_entries,
        page_size=1,
    )


def trade_leg(transaction: str = "synthetic-transaction") -> SwapLeg:
    return SwapLeg(
        transaction_hash=transaction,
        occurred_at=datetime(2026, 9, 1, 12, tzinfo=UTC),
        bought_address=TOKEN,
        bought_amount=Decimal("25"),
        sold_address=QUOTE,
        sold_amount=Decimal("2"),
        trade_value_usd=Decimal("2"),
    )


class FakeProvider:
    documented_credit_cost = 1

    def __init__(self, pages: dict[int, tuple[tuple[SwapLeg, ...], bool]]) -> None:
        self.pages = pages
        self.calls = 0

    def fingerprint(self, query: WalletTradeQuery) -> str:
        return hashlib.sha256(f"page:{query.page}".encode()).hexdigest()

    def fetch_page(self, query: WalletTradeQuery, *, max_attempts: int) -> WalletTradePage:
        self.calls += 1
        legs, is_last = self.pages[query.page]
        return WalletTradePage(
            legs=legs,
            request_fingerprint=self.fingerprint(query),
            response_hash=hashlib.sha256(f"response:{query.page}".encode()).hexdigest(),
            retrieved_at=NOW,
            page=query.page,
            per_page=query.per_page,
            is_last_page=is_last,
            request_id=f"request-{query.page}",
            quoted_credits=1,
            used_credits=1,
            attempt_count=1,
        )


def repository(tmp_path: Path) -> SqliteIngestionRepository:
    return SqliteIngestionRepository(tmp_path / "entryglass.sqlite3")


def test_paginated_import_is_idempotent_and_second_run_uses_cache(tmp_path: Path) -> None:
    storage = repository(tmp_path)
    provider = FakeProvider({1: ((trade_leg(),), False), 2: ((), True)})
    use_case = ImportWalletEntries(provider=provider, repository=storage, clock=lambda: NOW)
    announced = []

    first = use_case.execute(scope(), on_job_created=announced.append)
    second = use_case.execute(scope())

    assert announced[0].status is ImportStatus.RUNNING
    assert announced[0].job_id == first.job_id
    assert first.status is ImportStatus.COMPLETE
    assert first.coverage is CoverageState.OBSERVED
    assert first.entries_saved == 1
    assert first.pages_fetched == 2
    assert first.requests_attempted == 2
    assert first.credits_used == 2
    assert second.status is ImportStatus.COMPLETE
    assert second.entries_saved == 1
    assert second.requests_attempted == 0
    assert second.credits_used == 0
    assert provider.calls == 2
    assert len(storage.list_entries(WALLET)) == 1
    assert stat.S_IMODE((tmp_path / "entryglass.sqlite3").stat().st_mode) == 0o600
    first_evidence = storage.list_evidence(first.job_id)
    assert first_evidence[0].subject_hash != WALLET
    assert first_evidence[0].requested_from_utc == scope().from_utc
    assert len(first_evidence[0].response_hash) == 64
    assert all(record.cache_hit for record in storage.list_evidence(second.job_id))


def test_budget_exhaustion_is_partial_not_zero_activity(tmp_path: Path) -> None:
    storage = repository(tmp_path)
    provider = FakeProvider(
        {
            1: (
                (
                    trade_leg("tx-complete"),
                    trade_leg("tx-boundary"),
                ),
                False,
            )
        }
    )
    result = ImportWalletEntries(provider=provider, repository=storage, clock=lambda: NOW).execute(
        scope(requests=1, credits=1)
    )

    assert result.status is ImportStatus.PARTIAL
    assert result.coverage is CoverageState.BUDGET_EXCEEDED
    assert result.entries_saved == 1
    assert result.error_code == "budget_exceeded"


def test_entry_limit_records_explicit_truncation(tmp_path: Path) -> None:
    storage = repository(tmp_path)
    provider = FakeProvider({1: ((trade_leg("tx-complete"), trade_leg("tx-boundary")), False)})
    result = ImportWalletEntries(provider=provider, repository=storage, clock=lambda: NOW).execute(
        scope(max_entries=1)
    )
    assert result.status is ImportStatus.PARTIAL
    assert result.coverage is CoverageState.PARTIAL_TRUNCATED
    assert result.error_code == "entry_limit_reached"


def test_empty_final_page_is_no_activity(tmp_path: Path) -> None:
    storage = repository(tmp_path)
    provider = FakeProvider({1: ((), True)})
    result = ImportWalletEntries(provider=provider, repository=storage, clock=lambda: NOW).execute(
        scope()
    )
    assert result.status is ImportStatus.COMPLETE
    assert result.coverage is CoverageState.NO_ACTIVITY


def test_empty_non_final_page_is_explicitly_truncated(tmp_path: Path) -> None:
    storage = repository(tmp_path)
    provider = FakeProvider({1: ((), False)})
    result = ImportWalletEntries(provider=provider, repository=storage, clock=lambda: NOW).execute(
        scope()
    )
    assert result.status is ImportStatus.PARTIAL
    assert result.coverage is CoverageState.PARTIAL_TRUNCATED
    assert result.error_code == "empty_non_final_page"


def test_non_entry_activity_is_not_reported_as_an_empty_wallet(tmp_path: Path) -> None:
    storage = repository(tmp_path)
    exit_leg = SwapLeg(
        transaction_hash="tx-exit",
        occurred_at=datetime(2026, 9, 1, 12, tzinfo=UTC),
        bought_address=QUOTE,
        bought_amount=Decimal("2"),
        sold_address=TOKEN,
        sold_amount=Decimal("25"),
        trade_value_usd=Decimal("2"),
    )
    provider = FakeProvider({1: ((exit_leg,), True)})
    result = ImportWalletEntries(provider=provider, repository=storage, clock=lambda: NOW).execute(
        scope()
    )
    assert result.status is ImportStatus.COMPLETE
    assert result.coverage is CoverageState.NO_QUALIFYING_ENTRIES


def test_ambiguous_activity_has_its_own_coverage_state(tmp_path: Path) -> None:
    storage = repository(tmp_path)
    second_output = SwapLeg(
        transaction_hash="synthetic-transaction",
        occurred_at=datetime(2026, 9, 1, 12, tzinfo=UTC),
        bought_address=TOKEN_TWO,
        bought_amount=Decimal("5"),
        sold_address=QUOTE,
        sold_amount=Decimal("1"),
        trade_value_usd=Decimal("1"),
    )
    provider = FakeProvider({1: ((trade_leg(), second_output), True)})
    result = ImportWalletEntries(provider=provider, repository=storage, clock=lambda: NOW).execute(
        scope()
    )
    assert result.status is ImportStatus.COMPLETE
    assert result.coverage is CoverageState.AMBIGUOUS_ACTIVITY
    assert storage.list_ambiguities(result.job_id) == (
        ("synthetic-transaction", "multiple_output_tokens", 2),
    )


def test_provider_failure_is_not_reported_as_no_activity(tmp_path: Path) -> None:
    class FailingProvider(FakeProvider):
        def fetch_page(self, query: WalletTradeQuery, *, max_attempts: int) -> WalletTradePage:
            raise TradeProviderFailure("synthetic_failure", attempts=max_attempts)

    storage = repository(tmp_path)
    result = ImportWalletEntries(
        provider=FailingProvider({}), repository=storage, clock=lambda: NOW
    ).execute(scope())
    assert result.status is ImportStatus.FAILED
    assert result.coverage is CoverageState.PROVIDER_FAILURE
    assert result.error_code == "synthetic_failure"
    assert result.requests_attempted == 3


def test_cancellation_keeps_the_first_page_recoverable(tmp_path: Path) -> None:
    class CancellingRepository(SqliteIngestionRepository):
        def save_page_result(self, **kwargs: object) -> None:
            super().save_page_result(**kwargs)
            self.request_cancellation(str(kwargs["job_id"]))

    storage = CancellingRepository(tmp_path / "entryglass.sqlite3")
    provider = FakeProvider({1: ((trade_leg("tx-complete"), trade_leg("tx-boundary")), False)})
    result = ImportWalletEntries(provider=provider, repository=storage, clock=lambda: NOW).execute(
        scope()
    )
    assert result.status is ImportStatus.CANCELLED
    assert result.coverage is CoverageState.CANCELLED
    assert result.entries_saved == 1
    assert len(storage.list_entries(WALLET)) == 1
