"""M4 review-job, replay, outcome-reveal, and evidence HTTP contracts."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Protocol

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field, field_validator

from entryglass.application.ingestion import RequestBudget
from entryglass.application.reviews import ProviderEvidence, ReviewScope
from entryglass.core.config import Settings
from entryglass.domain.context import HistoricalContext
from entryglass.domain.outcomes import OutcomeObservation
from entryglass.domain.reviews import ReviewJob
from entryglass.domain.trades import QuoteAsset, TradeEntry
from entryglass.infrastructure.storage import SqliteIngestionRepository

router = APIRouter(prefix="/reviews", tags=["reviews"])

WSOL = QuoteAsset(
    address="So11111111111111111111111111111111111111112",
    symbol="SOL",
)
USDC = QuoteAsset(
    address="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
    symbol="USDC",
)


class ReviewRunner(Protocol):
    @property
    def provider_configured(self) -> bool: ...

    def create(self, scope: ReviewScope) -> ReviewJob: ...

    def cancel(self, review_id: str) -> ReviewJob: ...


class CreateReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    wallet_address: str = Field(min_length=32, max_length=44)
    from_utc: datetime
    to_utc: datetime
    max_entries: int | None = Field(default=None, ge=1, le=30)
    max_requests: int | None = Field(default=None, ge=1, le=100)
    max_credits: int | None = Field(default=None, ge=1, le=500)

    @field_validator("from_utc", "to_utc")
    @classmethod
    def timestamps_must_be_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Review timestamps must include a UTC offset.")
        return value.astimezone(UTC)


class ReviewResponse(BaseModel):
    review_id: str
    wallet_address: str
    from_utc: datetime
    to_utc: datetime
    status: str
    stage: str
    entries_total: int
    entries_processed: int
    requests_attempted: int
    credits_used: int
    max_entries: int
    max_requests: int
    max_credits: int
    cancellation_requested: bool
    error_code: str | None


class EntrySummary(BaseModel):
    entry_id: str
    occurred_at: datetime
    token_address: str
    quote_address: str
    trade_value_usd: Decimal
    context_coverage: str
    outcome_states: dict[str, str]


class ContextResponse(BaseModel):
    coverage: str
    window_from_utc: datetime
    window_to_utc: datetime
    smart_trader_net_flow_usd: Decimal | None
    smart_trader_avg_flow_usd: Decimal | None
    smart_trader_wallet_count: int | None
    warnings: tuple[str, ...]


class ReplayResponse(BaseModel):
    entry: EntrySummary
    token_amount: Decimal
    quote_amount: Decimal
    entry_price_usd: Decimal
    context: ContextResponse | None
    outcome_values_hidden: bool = True


class OutcomeResponse(BaseModel):
    horizon: str
    target_at: datetime
    state: str
    observed_at: datetime | None
    observed_price_usd: Decimal | None
    price_change_pct: Decimal | None
    interpretation: str = "Reference price change, not realized PnL."


class EvidenceResponse(BaseModel):
    kind: str
    source: str = "Nansen"
    endpoint: str
    requested_from_utc: datetime
    requested_to_utc: datetime
    retrieved_at: datetime
    request_id: str | None
    request_fingerprint: str
    response_hash: str
    warnings: tuple[str, ...]
    coverage: str
    quoted_credits: int | None
    used_credits: int | None
    attempt_count: int
    rule_version: str = "entryglass-methodology-v1"


def repository(request: Request) -> SqliteIngestionRepository:
    return request.app.state.review_repository


def runner(request: Request) -> ReviewRunner:
    return request.app.state.review_service


Repository = Annotated[SqliteIngestionRepository, Depends(repository)]
Runner = Annotated[ReviewRunner, Depends(runner)]


@router.post("", response_model=ReviewResponse, status_code=status.HTTP_202_ACCEPTED)
def create_review(
    payload: CreateReviewRequest,
    request: Request,
    service: Runner,
) -> ReviewResponse:
    settings: Settings = request.app.state.settings
    if not service.provider_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "provider_not_configured",
                "message": "Configure the server-side Nansen key to start a live review.",
            },
        )
    try:
        scope = ReviewScope(
            wallet_address=payload.wallet_address,
            from_utc=payload.from_utc,
            to_utc=payload.to_utc,
            quote_assets=(WSOL, USDC),
            budget=RequestBudget(
                max_requests=min(
                    payload.max_requests or settings.review_max_requests,
                    settings.review_max_requests,
                ),
                max_credits=min(
                    payload.max_credits or settings.review_max_credits,
                    settings.review_max_credits,
                ),
            ),
            max_entries=min(
                payload.max_entries or settings.review_max_entries,
                settings.review_max_entries,
            ),
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return _review_response(service.create(scope))


@router.get("/{review_id}", response_model=ReviewResponse)
def get_review(review_id: str, storage: Repository) -> ReviewResponse:
    return _review_response(_get_review(storage, review_id))


@router.post("/{review_id}/cancel", response_model=ReviewResponse)
def cancel_review(review_id: str, service: Runner) -> ReviewResponse:
    try:
        return _review_response(service.cancel(review_id))
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Review not found.") from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.get("/{review_id}/entries", response_model=list[EntrySummary])
def list_entries(review_id: str, storage: Repository) -> list[EntrySummary]:
    _get_review(storage, review_id)
    return [
        _entry_summary(storage, review_id, entry)
        for entry in storage.list_review_entries(review_id)
    ]


@router.get("/{review_id}/entries/{entry_id}", response_model=ReplayResponse)
def replay_entry(review_id: str, entry_id: str, storage: Repository) -> ReplayResponse:
    entry = _get_entry(storage, review_id, entry_id)
    context = storage.get_historical_context(review_id, entry_id)
    return ReplayResponse(
        entry=_entry_summary(storage, review_id, entry),
        token_amount=entry.token_amount,
        quote_amount=entry.quote_amount,
        entry_price_usd=entry.unit_price_usd,
        context=None if context is None else _context_response(context),
    )


@router.get(
    "/{review_id}/entries/{entry_id}/outcomes",
    response_model=list[OutcomeResponse],
)
def reveal_outcomes(review_id: str, entry_id: str, storage: Repository) -> list[OutcomeResponse]:
    _get_entry(storage, review_id, entry_id)
    return [_outcome_response(item) for item in storage.list_outcomes(review_id, entry_id)]


@router.get(
    "/{review_id}/entries/{entry_id}/evidence",
    response_model=list[EvidenceResponse],
)
def list_evidence(review_id: str, entry_id: str, storage: Repository) -> list[EvidenceResponse]:
    _get_entry(storage, review_id, entry_id)
    return [_evidence_response(item) for item in storage.list_review_evidence(review_id, entry_id)]


def _get_review(storage: SqliteIngestionRepository, review_id: str) -> ReviewJob:
    try:
        return storage.get_review(review_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Review not found.") from error


def _get_entry(storage: SqliteIngestionRepository, review_id: str, entry_id: str) -> TradeEntry:
    _get_review(storage, review_id)
    try:
        return storage.get_review_entry(review_id, entry_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Review entry not found.") from error


def _review_response(job: ReviewJob) -> ReviewResponse:
    return ReviewResponse(
        **{
            field: getattr(job, field)
            for field in ReviewResponse.model_fields
            if field not in {"status", "stage"}
        },
        status=job.status.value,
        stage=job.stage.value,
    )


def _entry_summary(
    storage: SqliteIngestionRepository, review_id: str, entry: TradeEntry
) -> EntrySummary:
    context = storage.get_historical_context(review_id, entry.entry_id)
    outcomes = storage.list_outcomes(review_id, entry.entry_id)
    return EntrySummary(
        entry_id=entry.entry_id,
        occurred_at=entry.occurred_at,
        token_address=entry.token_address,
        quote_address=entry.quote_address,
        trade_value_usd=entry.trade_value_usd,
        context_coverage="pending" if context is None else context.coverage.value,
        outcome_states={item.horizon.value: item.state.value for item in outcomes},
    )


def _context_response(context: HistoricalContext) -> ContextResponse:
    return ContextResponse(
        coverage=context.coverage.value,
        window_from_utc=context.window.from_utc,
        window_to_utc=context.window.to_utc,
        smart_trader_net_flow_usd=context.smart_trader_net_flow_usd,
        smart_trader_avg_flow_usd=context.smart_trader_avg_flow_usd,
        smart_trader_wallet_count=context.smart_trader_wallet_count,
        warnings=context.warnings,
    )


def _outcome_response(outcome: OutcomeObservation) -> OutcomeResponse:
    return OutcomeResponse(
        horizon=outcome.horizon.value,
        target_at=outcome.target_at,
        state=outcome.state.value,
        observed_at=outcome.observed_at,
        observed_price_usd=outcome.observed_price_usd,
        price_change_pct=outcome.price_change_pct,
    )


def _evidence_response(evidence: ProviderEvidence) -> EvidenceResponse:
    return EvidenceResponse(
        kind=evidence.kind,
        endpoint=evidence.endpoint,
        requested_from_utc=evidence.requested_from_utc,
        requested_to_utc=evidence.requested_to_utc,
        retrieved_at=evidence.retrieved_at,
        request_id=evidence.request_id,
        request_fingerprint=evidence.request_fingerprint,
        response_hash=evidence.response_hash,
        warnings=evidence.warnings,
        coverage=("truncated" if evidence.truncated else "complete"),
        quoted_credits=evidence.quoted_credits,
        used_credits=evidence.used_credits,
        attempt_count=evidence.attempt_count,
    )
