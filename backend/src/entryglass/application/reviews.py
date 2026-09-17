"""M3 orchestration for strictly separated context and later outcomes."""

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Protocol

from entryglass.application.ingestion import (
    ImportScope,
    ImportWalletEntries,
    IngestionRepository,
    RequestBudget,
    TradeProviderFailure,
    WalletTradeProvider,
)
from entryglass.domain.context import HistoricalContext, PreEntryWindow
from entryglass.domain.outcomes import OutcomeHorizon, OutcomeObservation, OutcomeState
from entryglass.domain.reviews import ReviewJob, ReviewStage, ReviewStatus
from entryglass.domain.trades import QuoteAsset, TradeEntry, validate_solana_address


@dataclass(frozen=True, slots=True)
class ReviewScope:
    wallet_address: str
    from_utc: datetime
    to_utc: datetime
    quote_assets: tuple[QuoteAsset, ...]
    budget: RequestBudget
    max_entries: int = 5

    def __post_init__(self) -> None:
        validate_solana_address(self.wallet_address)
        _require_utc(self.from_utc)
        _require_utc(self.to_utc)
        if self.from_utc >= self.to_utc or self.to_utc - self.from_utc > timedelta(days=90):
            raise ValueError("A review window must be positive and no longer than 90 days.")
        if not 1 <= self.max_entries <= 30:
            raise ValueError("A review supports between 1 and 30 entries.")
        if not self.quote_assets:
            raise ValueError("At least one quote asset is required.")


@dataclass(frozen=True, slots=True)
class ProviderEvidence:
    kind: str
    endpoint: str
    subject_hash: str
    request_fingerprint: str
    response_hash: str
    requested_from_utc: datetime
    requested_to_utc: datetime
    retrieved_at: datetime
    request_id: str | None
    warnings: tuple[str, ...]
    quoted_credits: int | None
    used_credits: int | None
    attempt_count: int
    truncated: bool = False
    truncation_note: str | None = None


@dataclass(frozen=True, slots=True)
class ContextFetch:
    context: HistoricalContext
    evidence: ProviderEvidence


@dataclass(frozen=True, slots=True)
class PriceCandle:
    interval_start: datetime
    close: Decimal | None

    def __post_init__(self) -> None:
        _require_utc(self.interval_start)
        if self.close is not None and self.close < 0:
            raise ValueError("Candle close cannot be negative.")


@dataclass(frozen=True, slots=True)
class PriceFetch:
    candles: tuple[PriceCandle, ...]
    evidence: ProviderEvidence


class HistoryProviderFailure(RuntimeError):
    def __init__(
        self,
        code: str,
        *,
        attempts: int,
        used_credits: int = 0,
        request_id: str | None = None,
    ) -> None:
        self.code = code
        self.attempts = attempts
        self.used_credits = used_credits
        self.request_id = request_id
        super().__init__(
            f"Historical provider failed (code={code}, request_id={request_id or 'missing'})."
        )


class HistoricalMarketProvider(Protocol):
    context_credit_cost: int
    price_credit_cost: int

    def fetch_context(
        self,
        entry: TradeEntry,
        window: PreEntryWindow,
        *,
        max_attempts: int,
    ) -> ContextFetch: ...

    def fetch_prices(
        self,
        entry: TradeEntry,
        *,
        from_utc: datetime,
        to_utc: datetime,
        max_attempts: int,
    ) -> PriceFetch: ...


class ReviewRepository(Protocol):
    def get_review(self, review_id: str) -> ReviewJob: ...

    def set_review_import(self, review_id: str, import_job_id: str) -> None: ...

    def set_review_stage(self, review_id: str, stage: ReviewStage) -> None: ...

    def review_cancellation_requested(self, review_id: str) -> bool: ...

    def list_job_entries(self, job_id: str) -> tuple[TradeEntry, ...]: ...

    def attach_review_entries(self, review_id: str, entries: tuple[TradeEntry, ...]) -> None: ...

    def save_review_entry(
        self,
        review_id: str,
        *,
        context: HistoricalContext,
        outcomes: tuple[OutcomeObservation, ...],
        evidence: tuple[ProviderEvidence, ...],
        requests_attempted: int,
        credits_used: int,
    ) -> None: ...

    def update_review_accounting(
        self,
        review_id: str,
        *,
        requests_attempted: int,
        credits_used: int,
    ) -> None: ...

    def finish_review(
        self,
        review_id: str,
        *,
        status: ReviewStatus,
        error_code: str | None = None,
    ) -> ReviewJob: ...


class BuildWalletReview:
    """Import entries, then enrich each through strictly separate data paths."""

    def __init__(
        self,
        *,
        wallet_provider: WalletTradeProvider,
        history_provider: HistoricalMarketProvider,
        ingestion_repository: IngestionRepository,
        review_repository: ReviewRepository,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        retry_limit: int = 1,
    ) -> None:
        self._wallet_provider = wallet_provider
        self._history_provider = history_provider
        self._ingestion_repository = ingestion_repository
        self._review_repository = review_repository
        self._clock = clock
        self._retry_limit = retry_limit

    def execute(self, review_id: str, scope: ReviewScope) -> ReviewJob:
        if self._review_repository.review_cancellation_requested(review_id):
            return self._review_repository.finish_review(
                review_id, status=ReviewStatus.CANCELLED, error_code="cancelled"
            )
        self._review_repository.set_review_stage(review_id, ReviewStage.IMPORTING_ENTRIES)
        import_budget = RequestBudget(
            max_requests=min(2, scope.budget.max_requests),
            max_credits=min(2, scope.budget.max_credits),
        )
        importer = ImportWalletEntries(
            provider=self._wallet_provider,
            repository=self._ingestion_repository,
            retry_limit=self._retry_limit,
            clock=self._clock,
        )
        try:
            import_job = importer.execute(
                ImportScope(
                    wallet_address=scope.wallet_address,
                    from_utc=scope.from_utc,
                    to_utc=scope.to_utc,
                    quote_assets=scope.quote_assets,
                    budget=import_budget,
                    max_entries=scope.max_entries,
                    page_size=100,
                ),
                on_job_created=lambda job: self._review_repository.set_review_import(
                    review_id, job.job_id
                ),
            )
        except TradeProviderFailure as error:
            self._review_repository.update_review_accounting(
                review_id,
                requests_attempted=error.attempts,
                credits_used=error.used_credits,
            )
            return self._review_repository.finish_review(
                review_id, status=ReviewStatus.FAILED, error_code=error.code
            )

        entries = self._review_repository.list_job_entries(import_job.job_id)
        self._review_repository.attach_review_entries(review_id, entries)
        requests_attempted = import_job.requests_attempted
        credits_used = import_job.credits_used
        self._review_repository.update_review_accounting(
            review_id,
            requests_attempted=requests_attempted,
            credits_used=credits_used,
        )
        if import_job.status.value in {"failed", "cancelled"}:
            status = (
                ReviewStatus.CANCELLED
                if import_job.status.value == "cancelled"
                else ReviewStatus.FAILED
            )
            return self._review_repository.finish_review(
                review_id, status=status, error_code=import_job.error_code
            )
        if not entries:
            status = (
                ReviewStatus.COMPLETE
                if import_job.status.value == "complete"
                else ReviewStatus.PARTIAL
            )
            return self._review_repository.finish_review(
                review_id, status=status, error_code=import_job.error_code
            )

        self._review_repository.set_review_stage(review_id, ReviewStage.ENRICHING_EVIDENCE)
        for entry in entries:
            if self._review_repository.review_cancellation_requested(review_id):
                return self._review_repository.finish_review(
                    review_id, status=ReviewStatus.CANCELLED, error_code="cancelled"
                )

            remaining_requests = scope.budget.max_requests - requests_attempted
            remaining_credits = scope.budget.max_credits - credits_used
            if (
                remaining_requests < 1
                or remaining_credits < self._history_provider.context_credit_cost
            ):
                return self._review_repository.finish_review(
                    review_id,
                    status=ReviewStatus.PARTIAL,
                    error_code="budget_exceeded",
                )
            window = PreEntryWindow.before(entry.occurred_at)
            try:
                context_fetch = self._history_provider.fetch_context(
                    entry,
                    window,
                    max_attempts=_allowed_attempts(
                        retry_limit=self._retry_limit,
                        remaining_requests=remaining_requests,
                        remaining_credits=remaining_credits,
                        cost=self._history_provider.context_credit_cost,
                    ),
                )
            except HistoryProviderFailure as error:
                requests_attempted += error.attempts
                credits_used += error.used_credits
                self._review_repository.update_review_accounting(
                    review_id,
                    requests_attempted=requests_attempted,
                    credits_used=credits_used,
                )
                current = self._review_repository.get_review(review_id)
                return self._review_repository.finish_review(
                    review_id,
                    status=(
                        ReviewStatus.PARTIAL if current.entries_processed else ReviewStatus.FAILED
                    ),
                    error_code=error.code,
                )
            requests_attempted += context_fetch.evidence.attempt_count
            credits_used += _used_or_documented(
                context_fetch.evidence,
                self._history_provider.context_credit_cost,
            )

            outcomes, price_evidence, request_delta, credit_delta, error = self._outcomes(
                entry,
                remaining_requests=scope.budget.max_requests - requests_attempted,
                remaining_credits=scope.budget.max_credits - credits_used,
            )
            if error is not None:
                requests_attempted += request_delta
                credits_used += credit_delta
                self._review_repository.save_review_entry(
                    review_id,
                    context=context_fetch.context,
                    outcomes=outcomes,
                    evidence=(context_fetch.evidence,),
                    requests_attempted=requests_attempted,
                    credits_used=credits_used,
                )
                return self._review_repository.finish_review(
                    review_id,
                    status=ReviewStatus.PARTIAL,
                    error_code=error,
                )
            requests_attempted += request_delta
            credits_used += credit_delta
            evidence = (context_fetch.evidence,) + (
                (price_evidence,) if price_evidence is not None else ()
            )
            self._review_repository.save_review_entry(
                review_id,
                context=context_fetch.context,
                outcomes=outcomes,
                evidence=evidence,
                requests_attempted=requests_attempted,
                credits_used=credits_used,
            )

        final_status = (
            ReviewStatus.PARTIAL if import_job.status.value == "partial" else ReviewStatus.COMPLETE
        )
        return self._review_repository.finish_review(
            review_id,
            status=final_status,
            error_code=import_job.error_code if final_status is ReviewStatus.PARTIAL else None,
        )

    def _outcomes(
        self,
        entry: TradeEntry,
        *,
        remaining_requests: int,
        remaining_credits: int,
    ) -> tuple[
        tuple[OutcomeObservation, ...],
        ProviderEvidence | None,
        int,
        int,
        str | None,
    ]:
        now = self._clock()
        pending: list[OutcomeObservation] = []
        reached: list[OutcomeHorizon] = []
        for horizon in OutcomeHorizon:
            if now < entry.occurred_at + horizon.duration:
                pending.append(
                    OutcomeObservation.from_price(
                        entry_id=entry.entry_id,
                        horizon=horizon,
                        entry_at=entry.occurred_at,
                        entry_price_usd=entry.unit_price_usd,
                        as_of=now,
                        observed_at=None,
                        observed_price_usd=None,
                    )
                )
            else:
                reached.append(horizon)
        if not reached:
            return tuple(pending), None, 0, 0, None
        if remaining_requests < 1 or remaining_credits < self._history_provider.price_credit_cost:
            unavailable = pending + [
                OutcomeObservation.unavailable(
                    entry_id=entry.entry_id,
                    horizon=horizon,
                    entry_at=entry.occurred_at,
                    state=OutcomeState.BUDGET_EXCEEDED,
                )
                for horizon in reached
            ]
            unavailable.sort(key=lambda item: item.horizon.duration)
            return tuple(unavailable), None, 0, 0, "budget_exceeded"

        first_target = min(entry.occurred_at + item.duration for item in reached)
        last_target = max(entry.occurred_at + item.duration for item in reached)
        query_to = min(now, last_target + timedelta(hours=2))
        if query_to <= first_target:
            query_to = first_target + timedelta(hours=1)
        try:
            fetched = self._history_provider.fetch_prices(
                entry,
                from_utc=first_target,
                to_utc=query_to,
                max_attempts=_allowed_attempts(
                    retry_limit=self._retry_limit,
                    remaining_requests=remaining_requests,
                    remaining_credits=remaining_credits,
                    cost=self._history_provider.price_credit_cost,
                ),
            )
        except HistoryProviderFailure as error:
            unavailable = pending + [
                OutcomeObservation.unavailable(
                    entry_id=entry.entry_id,
                    horizon=horizon,
                    entry_at=entry.occurred_at,
                    state=OutcomeState.PROVIDER_FAILURE,
                )
                for horizon in reached
            ]
            unavailable.sort(key=lambda item: item.horizon.duration)
            return (
                tuple(unavailable),
                None,
                error.attempts,
                error.used_credits,
                error.code,
            )

        observed = list(pending)
        for horizon in reached:
            target = entry.occurred_at + horizon.duration
            candle = next(
                (
                    item
                    for item in fetched.candles
                    if item.interval_start >= target
                    and item.interval_start + timedelta(hours=1) <= now
                    and item.close is not None
                ),
                None,
            )
            if candle is None:
                state = (
                    OutcomeState.TRUNCATED
                    if fetched.evidence.truncated
                    else OutcomeState.MISSING_PRICE
                )
                observed.append(
                    OutcomeObservation.unavailable(
                        entry_id=entry.entry_id,
                        horizon=horizon,
                        entry_at=entry.occurred_at,
                        state=state,
                    )
                )
            else:
                observed.append(
                    OutcomeObservation.from_price(
                        entry_id=entry.entry_id,
                        horizon=horizon,
                        entry_at=entry.occurred_at,
                        entry_price_usd=entry.unit_price_usd,
                        as_of=now,
                        observed_at=candle.interval_start,
                        observed_price_usd=candle.close,
                    )
                )
        observed.sort(key=lambda item: item.horizon.duration)
        return (
            tuple(observed),
            fetched.evidence,
            fetched.evidence.attempt_count,
            _used_or_documented(
                fetched.evidence,
                self._history_provider.price_credit_cost,
            ),
            None,
        )


def evidence_id(review_id: str, entry_id: str, evidence: ProviderEvidence) -> str:
    value = f"{review_id}:{entry_id}:{evidence.kind}:{evidence.request_fingerprint}"
    return hashlib.sha256(value.encode()).hexdigest()


def _allowed_attempts(
    *, retry_limit: int, remaining_requests: int, remaining_credits: int, cost: int
) -> int:
    return max(1, min(retry_limit + 1, remaining_requests, remaining_credits // cost))


def _used_or_documented(evidence: ProviderEvidence, documented: int) -> int:
    if evidence.used_credits is not None:
        return evidence.used_credits
    return documented * evidence.attempt_count


def _require_utc(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError("Review timestamps must be UTC-aware.")
