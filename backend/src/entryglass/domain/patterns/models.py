"""Small predeclared rule set; no learned thresholds or probability claims."""

from decimal import Decimal
from enum import StrEnum

from entryglass.domain.context import ContextCoverage
from entryglass.domain.outcomes import OutcomeObservation, OutcomeState

FLOW_RULE_VERSION = "smart-trader-flow-v1"
FLAT_RETURN_BAND_PCT = Decimal("2")


class FlowPattern(StrEnum):
    NET_INFLOW = "smart_trader_net_inflow"
    NET_OUTFLOW = "smart_trader_net_outflow"
    NO_OBSERVED_FLOW = "smart_trader_no_observed_flow"
    ACTIVE_FLAT = "smart_trader_active_flat"
    UNAVAILABLE = "unavailable"


class OutcomeBand(StrEnum):
    GAIN = "gain"
    FLAT = "flat"
    DECLINE = "decline"
    UNAVAILABLE = "unavailable"


def classify_flow(
    *,
    coverage: ContextCoverage,
    net_flow_usd: Decimal | None,
    wallet_count: int | None,
) -> FlowPattern:
    """Classify only observed, comparable Smart Trader fields."""
    if coverage is ContextCoverage.UNAVAILABLE or net_flow_usd is None or wallet_count is None:
        return FlowPattern.UNAVAILABLE
    if net_flow_usd > 0:
        return FlowPattern.NET_INFLOW
    if net_flow_usd < 0:
        return FlowPattern.NET_OUTFLOW
    if wallet_count == 0:
        return FlowPattern.NO_OBSERVED_FLOW
    return FlowPattern.ACTIVE_FLAT


def classify_outcome(outcome: OutcomeObservation | None) -> OutcomeBand:
    if (
        outcome is None
        or outcome.state is not OutcomeState.OBSERVED
        or outcome.price_change_pct is None
    ):
        return OutcomeBand.UNAVAILABLE
    if outcome.price_change_pct > FLAT_RETURN_BAND_PCT:
        return OutcomeBand.GAIN
    if outcome.price_change_pct < -FLAT_RETURN_BAND_PCT:
        return OutcomeBand.DECLINE
    return OutcomeBand.FLAT


def rule_description(pattern: FlowPattern) -> str:
    return {
        FlowPattern.NET_INFLOW: "Observed Smart Trader net flow was above zero.",
        FlowPattern.NET_OUTFLOW: "Observed Smart Trader net flow was below zero.",
        FlowPattern.NO_OBSERVED_FLOW: (
            "Observed Smart Trader net flow and wallet count were both zero."
        ),
        FlowPattern.ACTIVE_FLAT: (
            "Observed Smart Trader net flow was zero while wallet count was positive."
        ),
        FlowPattern.UNAVAILABLE: "Comparable Smart Trader fields were unavailable.",
    }[pattern]
