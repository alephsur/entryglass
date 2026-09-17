"""Immutable evidence and recoverable import-job state."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Literal


class CoverageState(StrEnum):
    OBSERVED = "observed"
    NO_ACTIVITY = "no_activity"
    NO_QUALIFYING_ENTRIES = "no_qualifying_entries"
    AMBIGUOUS_ACTIVITY = "ambiguous_activity"
    PARTIAL_TRUNCATED = "partial_truncated"
    PROVIDER_FAILURE = "provider_failure"
    BUDGET_EXCEEDED = "budget_exceeded"
    CANCELLED = "cancelled"
    UNAVAILABLE = "unavailable"


class ImportStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETE = "complete"
    PARTIAL = "partial"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class EvidenceRecord:
    """Safe, immutable evidence metadata; no provider row values are included."""

    evidence_id: str
    job_id: str
    provider: str
    endpoint: str
    chain: Literal["solana"]
    subject_hash: str
    requested_from_utc: datetime
    requested_to_utc: datetime
    request_fingerprint: str
    response_hash: str
    retrieved_at: datetime
    adapter_version: str
    methodology_version: str
    source_schema_version: str
    request_id: str | None = None
    page: int | None = None
    per_page: int | None = None
    is_last_page: bool | None = None
    warnings: tuple[str, ...] = ()
    quoted_credits: int | None = None
    used_credits: int | None = None
    attempt_count: int = 1
    cache_hit: bool = False

    def __post_init__(self) -> None:
        required = (
            self.evidence_id,
            self.job_id,
            self.provider,
            self.endpoint,
            self.subject_hash,
            self.request_fingerprint,
            self.response_hash,
            self.adapter_version,
            self.methodology_version,
            self.source_schema_version,
        )
        if not all(value.strip() for value in required):
            raise ValueError("Evidence identifiers and versions are required.")
        _require_utc(self.retrieved_at)
        _require_utc(self.requested_from_utc)
        _require_utc(self.requested_to_utc)
        if self.requested_from_utc >= self.requested_to_utc:
            raise ValueError("An evidence request window must have positive duration.")
        if self.attempt_count < 0 or self.quoted_credits is not None and self.quoted_credits < 0:
            raise ValueError("Evidence accounting values cannot be negative.")
        if self.used_credits is not None and self.used_credits < 0:
            raise ValueError("Evidence credit use cannot be negative.")


@dataclass(frozen=True, slots=True)
class ImportJob:
    job_id: str
    scope_key: str
    wallet_address: str
    from_utc: datetime
    to_utc: datetime
    status: ImportStatus
    coverage: CoverageState
    next_page: int = 1
    pages_fetched: int = 0
    requests_attempted: int = 0
    credits_used: int = 0
    entries_saved: int = 0
    cancellation_requested: bool = False
    error_code: str | None = None

    def __post_init__(self) -> None:
        for value in (self.job_id, self.scope_key, self.wallet_address):
            if not value.strip():
                raise ValueError("Import job identifiers are required.")
        _require_utc(self.from_utc)
        _require_utc(self.to_utc)
        if self.from_utc >= self.to_utc:
            raise ValueError("An import window must have positive duration.")
        counters = (
            self.next_page,
            self.pages_fetched,
            self.requests_attempted,
            self.credits_used,
            self.entries_saved,
        )
        if self.next_page < 1 or any(value < 0 for value in counters[1:]):
            raise ValueError("Import job counters cannot be negative.")


def _require_utc(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError("Evidence timestamps must be UTC-aware.")
