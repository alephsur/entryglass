"""Budgeted wallet-entry ingestion orchestration."""

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from typing import Protocol

from entryglass.domain.evidence import CoverageState, EvidenceRecord, ImportJob, ImportStatus
from entryglass.domain.trades import (
    AmbiguousTrade,
    QuoteAsset,
    SwapLeg,
    TradeEntry,
    normalize_trade_legs,
    validate_solana_address,
)


@dataclass(frozen=True, slots=True)
class RequestBudget:
    max_requests: int
    max_credits: int

    def __post_init__(self) -> None:
        if self.max_requests < 1 or self.max_credits < 1:
            raise ValueError("Request and credit budgets must be positive.")


@dataclass(frozen=True, slots=True)
class ImportScope:
    wallet_address: str
    from_utc: datetime
    to_utc: datetime
    quote_assets: tuple[QuoteAsset, ...]
    budget: RequestBudget
    max_entries: int = 30
    page_size: int = 100
    chain: str = "solana"

    def __post_init__(self) -> None:
        if self.chain != "solana":
            raise ValueError("The first Entryglass release supports Solana only.")
        validate_solana_address(self.wallet_address)
        _require_utc(self.from_utc)
        _require_utc(self.to_utc)
        if self.from_utc >= self.to_utc:
            raise ValueError("An import window must have positive duration.")
        if self.to_utc - self.from_utc > timedelta(days=90):
            raise ValueError("The first release limits wallet imports to 90 days.")
        if not 1 <= self.max_entries <= 30:
            raise ValueError("The first release allows between 1 and 30 entries.")
        if not 1 <= self.page_size <= 1000:
            raise ValueError("Provider page size must be between 1 and 1000.")
        if not self.quote_assets:
            raise ValueError("At least one quote asset is required.")
        if len({asset.address for asset in self.quote_assets}) != len(self.quote_assets):
            raise ValueError("Quote asset addresses must be unique.")

    @property
    def scope_key(self) -> str:
        payload = {
            "chain": self.chain,
            "from": _serialize_time(self.from_utc),
            "max_entries": self.max_entries,
            "page_size": self.page_size,
            "quotes": sorted(asset.address for asset in self.quote_assets),
            "to": _serialize_time(self.to_utc),
            "wallet": self.wallet_address,
        }
        encoded = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
        return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True, slots=True)
class WalletTradeQuery:
    wallet_address: str
    from_utc: datetime
    to_utc: datetime
    page: int
    per_page: int
    chain: str = "solana"


@dataclass(frozen=True, slots=True)
class WalletTradePage:
    legs: tuple[SwapLeg, ...]
    request_fingerprint: str
    response_hash: str
    retrieved_at: datetime
    page: int
    per_page: int
    is_last_page: bool
    warnings: tuple[str, ...] = ()
    request_id: str | None = None
    quoted_credits: int | None = None
    used_credits: int | None = None
    attempt_count: int = 1
    cache_hit: bool = False


class TradeProviderFailure(RuntimeError):
    """Safe provider failure with accounting, never raw response content."""

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
        message = (
            f"Wallet trade provider failed (code={code}, request_id={request_id or 'missing'})."
        )
        super().__init__(message)


class WalletTradeProvider(Protocol):
    documented_credit_cost: int

    def fingerprint(self, query: WalletTradeQuery) -> str: ...

    def fetch_page(self, query: WalletTradeQuery, *, max_attempts: int) -> WalletTradePage: ...


class IngestionRepository(Protocol):
    def create_job(self, scope: ImportScope, *, now: datetime) -> ImportJob: ...

    def get_job(self, job_id: str) -> ImportJob: ...

    def cancellation_requested(self, job_id: str) -> bool: ...

    def get_cached_page(self, fingerprint: str, *, now: datetime) -> WalletTradePage | None: ...

    def save_cached_page(self, page: WalletTradePage, *, expires_at: datetime) -> None: ...

    def save_page_result(
        self,
        *,
        job_id: str,
        wallet_address: str,
        entries: tuple[TradeEntry, ...],
        ambiguous: tuple[AmbiguousTrade, ...],
        evidence: EvidenceRecord,
        next_page: int,
        requests_attempted: int,
        credits_used: int,
    ) -> None: ...

    def finish_job(
        self,
        job_id: str,
        *,
        status: ImportStatus,
        coverage: CoverageState,
        error_code: str | None = None,
    ) -> ImportJob: ...

    def record_failed_attempts(
        self,
        job_id: str,
        *,
        requests_attempted: int,
        credits_used: int,
    ) -> None: ...


class ImportWalletEntries:
    """Import one bounded wallet window and persist recoverable progress."""

    def __init__(
        self,
        *,
        provider: WalletTradeProvider,
        repository: IngestionRepository,
        cache_ttl: timedelta = timedelta(hours=24),
        retry_limit: int = 2,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        if cache_ttl <= timedelta(0) or retry_limit < 0:
            raise ValueError("Cache TTL must be positive and retry limit cannot be negative.")
        self._provider = provider
        self._repository = repository
        self._cache_ttl = cache_ttl
        self._retry_limit = retry_limit
        self._clock = clock

    def execute(
        self,
        scope: ImportScope,
        *,
        on_job_created: Callable[[ImportJob], None] | None = None,
    ) -> ImportJob:
        job = self._repository.create_job(scope, now=self._clock())
        if on_job_created is not None:
            on_job_created(job)
        legs: list[SwapLeg] = []
        requests_attempted = 0
        credits_used = 0
        page_number = 1
        boundary_transaction: str | None = None

        while True:
            if self._repository.cancellation_requested(job.job_id):
                return self._repository.finish_job(
                    job.job_id,
                    status=ImportStatus.CANCELLED,
                    coverage=CoverageState.CANCELLED,
                )

            query = WalletTradeQuery(
                wallet_address=scope.wallet_address,
                from_utc=scope.from_utc,
                to_utc=scope.to_utc,
                page=page_number,
                per_page=scope.page_size,
            )
            fingerprint = self._provider.fingerprint(query)
            page = self._repository.get_cached_page(fingerprint, now=self._clock())
            if page is not None:
                page = replace(page, attempt_count=0, used_credits=0, cache_hit=True)
            else:
                remaining_requests = scope.budget.max_requests - requests_attempted
                if (
                    remaining_requests < 1
                    or credits_used + self._provider.documented_credit_cost
                    > scope.budget.max_credits
                ):
                    return self._repository.finish_job(
                        job.job_id,
                        status=ImportStatus.PARTIAL,
                        coverage=CoverageState.BUDGET_EXCEEDED,
                        error_code="budget_exceeded",
                    )
                try:
                    remaining_credit_attempts = (
                        scope.budget.max_credits - credits_used
                    ) // self._provider.documented_credit_cost
                    page = self._provider.fetch_page(
                        query,
                        max_attempts=min(
                            self._retry_limit + 1,
                            remaining_requests,
                            remaining_credit_attempts,
                        ),
                    )
                except TradeProviderFailure as error:
                    requests_attempted += error.attempts
                    credits_used += error.used_credits
                    self._repository.record_failed_attempts(
                        job.job_id,
                        requests_attempted=requests_attempted,
                        credits_used=credits_used,
                    )
                    return self._repository.finish_job(
                        job.job_id,
                        status=ImportStatus.PARTIAL if legs else ImportStatus.FAILED,
                        coverage=CoverageState.PROVIDER_FAILURE,
                        error_code=error.code,
                    )
                self._repository.save_cached_page(
                    page,
                    expires_at=self._clock() + self._cache_ttl,
                )

            requests_attempted += page.attempt_count
            credits_used += (
                page.used_credits
                if page.used_credits is not None
                else self._provider.documented_credit_cost * page.attempt_count
            )
            legs.extend(page.legs)
            normalizable_legs = legs
            if not page.is_last_page:
                if page.legs:
                    boundary_transaction = page.legs[-1].transaction_hash
                normalizable_legs = [
                    leg for leg in legs if leg.transaction_hash != boundary_transaction
                ]
            normalized = normalize_trade_legs(tuple(normalizable_legs), scope.quote_assets)
            entries = normalized.entries[: scope.max_entries]
            evidence = _evidence_for(job.job_id, query, page)
            self._repository.save_page_result(
                job_id=job.job_id,
                wallet_address=scope.wallet_address,
                entries=entries,
                ambiguous=normalized.ambiguous,
                evidence=evidence,
                next_page=page_number + 1,
                requests_attempted=requests_attempted,
                credits_used=credits_used,
            )

            if credits_used > scope.budget.max_credits:
                return self._repository.finish_job(
                    job.job_id,
                    status=ImportStatus.PARTIAL,
                    coverage=CoverageState.BUDGET_EXCEEDED,
                    error_code="reported_credit_use_exceeded_budget",
                )
            if not page.legs and not page.is_last_page:
                return self._repository.finish_job(
                    job.job_id,
                    status=ImportStatus.PARTIAL,
                    coverage=CoverageState.PARTIAL_TRUNCATED,
                    error_code="empty_non_final_page",
                )
            if page.is_last_page:
                if entries:
                    final_coverage = CoverageState.OBSERVED
                elif normalized.ambiguous:
                    final_coverage = CoverageState.AMBIGUOUS_ACTIVITY
                elif legs:
                    final_coverage = CoverageState.NO_QUALIFYING_ENTRIES
                else:
                    final_coverage = CoverageState.NO_ACTIVITY
                return self._repository.finish_job(
                    job.job_id,
                    status=ImportStatus.COMPLETE,
                    coverage=final_coverage,
                )
            if len(entries) >= scope.max_entries:
                return self._repository.finish_job(
                    job.job_id,
                    status=ImportStatus.PARTIAL,
                    coverage=CoverageState.PARTIAL_TRUNCATED,
                    error_code="entry_limit_reached",
                )
            page_number += 1


def _evidence_for(job_id: str, query: WalletTradeQuery, page: WalletTradePage) -> EvidenceRecord:
    identity = f"{job_id}:{page.request_fingerprint}:{page.cache_hit}"
    return EvidenceRecord(
        evidence_id=hashlib.sha256(identity.encode()).hexdigest(),
        job_id=job_id,
        provider="nansen",
        endpoint="/api/v1/profiler/dex-trades",
        chain="solana",
        subject_hash=hashlib.sha256(query.wallet_address.encode()).hexdigest(),
        requested_from_utc=query.from_utc,
        requested_to_utc=query.to_utc,
        request_fingerprint=page.request_fingerprint,
        response_hash=page.response_hash,
        retrieved_at=page.retrieved_at,
        adapter_version="nansen-wallet-trades-v1",
        methodology_version="m2-v1",
        source_schema_version="2026-09-16",
        request_id=page.request_id,
        page=page.page,
        per_page=page.per_page,
        is_last_page=page.is_last_page,
        warnings=page.warnings,
        quoted_credits=page.quoted_credits,
        used_credits=page.used_credits,
        attempt_count=page.attempt_count,
        cache_hit=page.cache_hit,
    )


def _require_utc(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError("Import timestamps must be UTC-aware.")


def _serialize_time(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")
