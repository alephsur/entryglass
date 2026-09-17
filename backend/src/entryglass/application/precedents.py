"""Deterministic, descriptive precedents and current-context comparison."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Protocol

from entryglass.domain.context import HistoricalContext
from entryglass.domain.outcomes import OutcomeHorizon, OutcomeObservation
from entryglass.domain.patterns import (
    FLOW_RULE_VERSION,
    FlowPattern,
    OutcomeBand,
    classify_flow,
    classify_outcome,
    rule_description,
)
from entryglass.domain.preflight import CurrentContext
from entryglass.domain.trades import TradeEntry


@dataclass(frozen=True, slots=True)
class OutcomeCounts:
    gain: int = 0
    flat: int = 0
    decline: int = 0
    unavailable: int = 0


@dataclass(frozen=True, slots=True)
class PrecedentObservation:
    entry_id: str
    occurred_at: datetime
    token_address: str
    pattern: FlowPattern
    outcome_band: OutcomeBand
    price_change_pct: Decimal | None


@dataclass(frozen=True, slots=True)
class PatternSummary:
    pattern: FlowPattern
    description: str
    sample_count: int
    outcome_counts: OutcomeCounts
    observations: tuple[PrecedentObservation, ...]


@dataclass(frozen=True, slots=True)
class PrecedentReport:
    review_id: str
    horizon: OutcomeHorizon
    rule_version: str
    patterns: tuple[PatternSummary, ...]
    baseline: OutcomeCounts
    context_observed: int
    context_unavailable: int
    evaluation_mode: str = "descriptive_only"
    evaluation_status: str = "not_run_no_predictive_claim"
    limitations: tuple[str, ...] = (
        "Patterns are descriptive personal precedents, not probabilities.",
        "No chronological held-out evaluation is reported because no predictive claim is made.",
        "Outcome horizons may overlap; they are not treated as independent evidence.",
    )


@dataclass(frozen=True, slots=True)
class PreflightComparison:
    pattern: FlowPattern
    rule_version: str
    comparable: bool
    matching_precedents: tuple[PrecedentObservation, ...]
    outcome_counts: OutcomeCounts
    missing_features: tuple[str, ...]
    differences: tuple[str, ...]
    limitations: tuple[str, ...]


class PrecedentRepository(Protocol):
    def list_review_entries(self, review_id: str) -> tuple[TradeEntry, ...]: ...

    def get_historical_context(self, review_id: str, entry_id: str) -> HistoricalContext | None: ...

    def list_outcomes(self, review_id: str, entry_id: str) -> tuple[OutcomeObservation, ...]: ...


def build_precedent_report(
    repository: PrecedentRepository,
    review_id: str,
    horizon: OutcomeHorizon,
) -> PrecedentReport:
    observations: list[PrecedentObservation] = []
    context_observed = 0
    context_unavailable = 0
    for entry in repository.list_review_entries(review_id):
        context = repository.get_historical_context(review_id, entry.entry_id)
        if context is None:
            pattern = FlowPattern.UNAVAILABLE
            context_unavailable += 1
        else:
            pattern = classify_flow(
                coverage=context.coverage,
                net_flow_usd=context.smart_trader_net_flow_usd,
                wallet_count=context.smart_trader_wallet_count,
            )
            if pattern is FlowPattern.UNAVAILABLE:
                context_unavailable += 1
            else:
                context_observed += 1
        outcome = next(
            (
                item
                for item in repository.list_outcomes(review_id, entry.entry_id)
                if item.horizon is horizon
            ),
            None,
        )
        observations.append(
            PrecedentObservation(
                entry_id=entry.entry_id,
                occurred_at=entry.occurred_at,
                token_address=entry.token_address,
                pattern=pattern,
                outcome_band=classify_outcome(outcome),
                price_change_pct=(None if outcome is None else outcome.price_change_pct),
            )
        )

    visible_patterns = (
        FlowPattern.NET_INFLOW,
        FlowPattern.NET_OUTFLOW,
        FlowPattern.NO_OBSERVED_FLOW,
        FlowPattern.ACTIVE_FLAT,
    )
    summaries = tuple(
        _summary(pattern, tuple(item for item in observations if item.pattern is pattern))
        for pattern in visible_patterns
    )
    return PrecedentReport(
        review_id=review_id,
        horizon=horizon,
        rule_version=FLOW_RULE_VERSION,
        patterns=summaries,
        baseline=_counts(tuple(observations)),
        context_observed=context_observed,
        context_unavailable=context_unavailable,
    )


def compare_current_context(
    current: CurrentContext,
    report: PrecedentReport,
) -> PreflightComparison:
    pattern = classify_flow(
        coverage=current.coverage,
        net_flow_usd=current.smart_trader_net_flow_usd,
        wallet_count=current.smart_trader_wallet_count,
    )
    missing: list[str] = []
    if current.smart_trader_net_flow_usd is None:
        missing.append("smart_trader_net_flow_usd")
    if current.smart_trader_wallet_count is None:
        missing.append("smart_trader_wallet_count")
    group = next((item for item in report.patterns if item.pattern is pattern), None)
    matches = () if group is None else group.observations
    differences: list[str] = []
    if pattern is not FlowPattern.UNAVAILABLE and not matches:
        differences.append("No historical entry in this review matched the current flow rule.")
    if current.smart_trader_avg_flow_usd is None:
        differences.append(
            "Average flow is unavailable and is excluded from the versioned comparison rule."
        )
    return PreflightComparison(
        pattern=pattern,
        rule_version=report.rule_version,
        comparable=pattern is not FlowPattern.UNAVAILABLE,
        matching_precedents=matches,
        outcome_counts=OutcomeCounts() if group is None else group.outcome_counts,
        missing_features=tuple(missing),
        differences=tuple(differences),
        limitations=(
            "Current data uses Nansen's rolling 1d timeframe; history uses an explicit "
            "24-hour UTC window.",
            "Freshness describes Entryglass retrieval age; the provider may cache the "
            "one-day response for 10 to 30 minutes.",
            "Only Smart Trader net-flow direction and observed wallet activity are compared.",
            "A match is a descriptive precedent, not a recommendation or risk probability.",
        ),
    )


def _summary(
    pattern: FlowPattern, observations: tuple[PrecedentObservation, ...]
) -> PatternSummary:
    return PatternSummary(
        pattern=pattern,
        description=rule_description(pattern),
        sample_count=len(observations),
        outcome_counts=_counts(observations),
        observations=observations,
    )


def _counts(observations: tuple[PrecedentObservation, ...]) -> OutcomeCounts:
    values = {band: 0 for band in OutcomeBand}
    for item in observations:
        values[item.outcome_band] += 1
    return OutcomeCounts(
        gain=values[OutcomeBand.GAIN],
        flat=values[OutcomeBand.FLAT],
        decline=values[OutcomeBand.DECLINE],
        unavailable=values[OutcomeBand.UNAVAILABLE],
    )
