"""Pure state for the M3/M4 review workflow."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum


class ReviewStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETE = "complete"
    PARTIAL = "partial"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ReviewStage(StrEnum):
    QUEUED = "queued"
    IMPORTING_ENTRIES = "importing_entries"
    ENRICHING_EVIDENCE = "enriching_evidence"
    COMPLETE = "complete"
    STOPPED = "stopped"


@dataclass(frozen=True, slots=True)
class ReviewJob:
    review_id: str
    wallet_address: str
    from_utc: datetime
    to_utc: datetime
    status: ReviewStatus
    stage: ReviewStage
    max_entries: int
    max_requests: int
    max_credits: int
    entries_total: int = 0
    entries_processed: int = 0
    requests_attempted: int = 0
    credits_used: int = 0
    import_job_id: str | None = None
    cancellation_requested: bool = False
    error_code: str | None = None

    def __post_init__(self) -> None:
        if not self.review_id.strip() or not self.wallet_address.strip():
            raise ValueError("Review identifiers are required.")
        for value in (self.from_utc, self.to_utc):
            if value.tzinfo is None or value.utcoffset() != timedelta(0):
                raise ValueError("Review timestamps must be UTC-aware.")
        if self.from_utc >= self.to_utc:
            raise ValueError("A review window must have positive duration.")
        limits = (self.max_entries, self.max_requests, self.max_credits)
        counters = (
            self.entries_total,
            self.entries_processed,
            self.requests_attempted,
            self.credits_used,
        )
        if any(value < 1 for value in limits) or any(value < 0 for value in counters):
            raise ValueError("Review limits must be positive and counters non-negative.")
        if self.entries_processed > self.entries_total:
            raise ValueError("Processed entries cannot exceed the review total.")
