"""M5 descriptive precedents and current-token preflight HTTP contracts."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Annotated, Literal, Protocol

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field

from entryglass.application.precedents import (
    OutcomeCounts,
    PatternSummary,
    PrecedentObservation,
    PrecedentReport,
    PreflightComparison,
    build_precedent_report,
    compare_current_context,
)
from entryglass.application.reviews import ProviderEvidence
from entryglass.domain.outcomes import OutcomeHorizon
from entryglass.domain.preflight import CurrentContext, PreflightJob
from entryglass.infrastructure.storage import SqliteIngestionRepository

router = APIRouter(prefix="/reviews/{review_id}", tags=["precedents"])


class PreflightRunner(Protocol):
    @property
    def provider_configured(self) -> bool: ...

    def create(self, review_id: str, token_address: str, horizon: str) -> PreflightJob: ...


class CountsResponse(BaseModel):
    gain: int
    flat: int
    decline: int
    unavailable: int


class ObservationResponse(BaseModel):
    entry_id: str
    occurred_at: datetime
    token_address: str
    pattern: str
    outcome_band: str
    price_change_pct: Decimal | None


class PatternResponse(BaseModel):
    pattern: str
    description: str
    sample_count: int
    outcome_counts: CountsResponse
    observations: list[ObservationResponse]


class PrecedentReportResponse(BaseModel):
    review_id: str
    horizon: str
    rule_version: str
    patterns: list[PatternResponse]
    baseline: CountsResponse
    context_observed: int
    context_unavailable: int
    evaluation_mode: str
    evaluation_status: str
    limitations: tuple[str, ...]


class CreatePreflightRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token_address: str = Field(min_length=32, max_length=44)
    horizon: Literal["24h", "7d"] = "7d"


class CurrentContextResponse(BaseModel):
    observed_at: datetime
    timeframe: str
    coverage: str
    smart_trader_net_flow_usd: Decimal | None
    smart_trader_avg_flow_usd: Decimal | None
    smart_trader_wallet_count: int | None
    warnings: tuple[str, ...]
    freshness: Literal["fresh", "stale"]
    freshness_basis: Literal["entryglass_retrieval_time"] = "entryglass_retrieval_time"


class ComparisonResponse(BaseModel):
    pattern: str
    rule_version: str
    comparable: bool
    matching_precedent_count: int
    matching_precedents: list[ObservationResponse]
    outcome_counts: CountsResponse
    missing_features: tuple[str, ...]
    differences: tuple[str, ...]
    limitations: tuple[str, ...]
    recommendation: None = None
    risk_score: None = None


class CurrentEvidenceResponse(BaseModel):
    source: str = "Nansen"
    endpoint: str
    timeframe: str = "1d"
    requested_from_utc: datetime
    requested_to_utc: datetime
    retrieved_at: datetime
    request_id: str | None
    warnings: tuple[str, ...]
    quoted_credits: int | None
    used_credits: int | None
    attempt_count: int


class PreflightResponse(BaseModel):
    preflight_id: str
    review_id: str
    token_address: str
    horizon: str
    status: str
    requests_attempted: int
    credits_used: int
    error_code: str | None
    current_context: CurrentContextResponse | None
    comparison: ComparisonResponse | None
    evidence: CurrentEvidenceResponse | None


def repository(request: Request) -> SqliteIngestionRepository:
    return request.app.state.review_repository


def preflight_runner(request: Request) -> PreflightRunner:
    return request.app.state.preflight_service


Repository = Annotated[SqliteIngestionRepository, Depends(repository)]
Runner = Annotated[PreflightRunner, Depends(preflight_runner)]


@router.get("/precedents", response_model=PrecedentReportResponse)
def precedents(
    review_id: str,
    storage: Repository,
    horizon: Literal["24h", "7d"] = "7d",
) -> PrecedentReportResponse:
    try:
        storage.get_review(review_id)
        report = build_precedent_report(storage, review_id, OutcomeHorizon(horizon))
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Review not found.") from error
    return _report_response(report)


@router.post(
    "/preflights",
    response_model=PreflightResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_preflight(
    review_id: str,
    payload: CreatePreflightRequest,
    service: Runner,
) -> PreflightResponse:
    if not service.provider_configured:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "provider_not_configured",
                "message": "Configure the server-side Nansen key to run preflight.",
            },
        )
    try:
        job = service.create(review_id, payload.token_address, payload.horizon)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Review not found.") from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return _preflight_response(job, None, None)


@router.get("/preflights/{preflight_id}", response_model=PreflightResponse)
def get_preflight(
    review_id: str,
    preflight_id: str,
    storage: Repository,
) -> PreflightResponse:
    try:
        job = storage.get_preflight(preflight_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="Preflight not found.") from error
    if job.review_id != review_id:
        raise HTTPException(status_code=404, detail="Preflight not found.")
    comparison = None
    if job.context is not None:
        report = build_precedent_report(storage, review_id, OutcomeHorizon(job.horizon))
        comparison = compare_current_context(job.context, report)
    evidence = storage.get_preflight_evidence(preflight_id)
    return _preflight_response(job, comparison, evidence)


def _counts_response(counts: OutcomeCounts) -> CountsResponse:
    return CountsResponse(
        gain=counts.gain,
        flat=counts.flat,
        decline=counts.decline,
        unavailable=counts.unavailable,
    )


def _observation_response(item: PrecedentObservation) -> ObservationResponse:
    return ObservationResponse(
        entry_id=item.entry_id,
        occurred_at=item.occurred_at,
        token_address=item.token_address,
        pattern=item.pattern.value,
        outcome_band=item.outcome_band.value,
        price_change_pct=item.price_change_pct,
    )


def _pattern_response(item: PatternSummary) -> PatternResponse:
    return PatternResponse(
        pattern=item.pattern.value,
        description=item.description,
        sample_count=item.sample_count,
        outcome_counts=_counts_response(item.outcome_counts),
        observations=[_observation_response(value) for value in item.observations],
    )


def _report_response(report: PrecedentReport) -> PrecedentReportResponse:
    return PrecedentReportResponse(
        review_id=report.review_id,
        horizon=report.horizon.value,
        rule_version=report.rule_version,
        patterns=[_pattern_response(item) for item in report.patterns],
        baseline=_counts_response(report.baseline),
        context_observed=report.context_observed,
        context_unavailable=report.context_unavailable,
        evaluation_mode=report.evaluation_mode,
        evaluation_status=report.evaluation_status,
        limitations=report.limitations,
    )


def _current_context_response(context: CurrentContext) -> CurrentContextResponse:
    age = datetime.now(UTC) - context.observed_at
    return CurrentContextResponse(
        observed_at=context.observed_at,
        timeframe=context.timeframe,
        coverage=context.coverage.value,
        smart_trader_net_flow_usd=context.smart_trader_net_flow_usd,
        smart_trader_avg_flow_usd=context.smart_trader_avg_flow_usd,
        smart_trader_wallet_count=context.smart_trader_wallet_count,
        warnings=context.warnings,
        freshness=("fresh" if timedelta(0) <= age <= timedelta(minutes=15) else "stale"),
    )


def _preflight_response(
    job: PreflightJob,
    comparison: PreflightComparison | None,
    evidence: ProviderEvidence | None,
) -> PreflightResponse:
    return PreflightResponse(
        preflight_id=job.preflight_id,
        review_id=job.review_id,
        token_address=job.token_address,
        horizon=job.horizon,
        status=job.status.value,
        requests_attempted=job.requests_attempted,
        credits_used=job.credits_used,
        error_code=job.error_code,
        current_context=(None if job.context is None else _current_context_response(job.context)),
        comparison=(
            None
            if comparison is None
            else ComparisonResponse(
                pattern=comparison.pattern.value,
                rule_version=comparison.rule_version,
                comparable=comparison.comparable,
                matching_precedent_count=len(comparison.matching_precedents),
                matching_precedents=[
                    _observation_response(item) for item in comparison.matching_precedents
                ],
                outcome_counts=_counts_response(comparison.outcome_counts),
                missing_features=comparison.missing_features,
                differences=comparison.differences,
                limitations=comparison.limitations,
            )
        ),
        evidence=(
            None
            if evidence is None
            else CurrentEvidenceResponse(
                endpoint=evidence.endpoint,
                requested_from_utc=evidence.requested_from_utc,
                requested_to_utc=evidence.requested_to_utc,
                retrieved_at=evidence.retrieved_at,
                request_id=evidence.request_id,
                warnings=evidence.warnings,
                quoted_credits=evidence.quoted_credits,
                used_credits=evidence.used_credits,
                attempt_count=evidence.attempt_count,
            )
        ),
    )
