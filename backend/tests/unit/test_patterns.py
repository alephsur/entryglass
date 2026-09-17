"""Verify the fixed M5 rules without mining the demonstration wallet."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from entryglass.application.precedents import (
    build_precedent_report,
    compare_current_context,
)
from entryglass.domain.context import ContextCoverage, HistoricalContext, PreEntryWindow
from entryglass.domain.outcomes import OutcomeHorizon, OutcomeObservation
from entryglass.domain.patterns import FlowPattern, OutcomeBand, classify_flow, classify_outcome
from entryglass.domain.preflight import CurrentContext
from entryglass.domain.trades import TradeEntry

TOKEN = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
TOKEN_TWO = "metaqbxxUerdq28cj1RbAWkYQm3ybzjb6a8bt518x1s"
QUOTE = "So11111111111111111111111111111111111111112"
ENTRY_AT = datetime(2026, 1, 1, 12, tzinfo=UTC)


def trade(entry_id: str, token: str, days: int) -> TradeEntry:
    return TradeEntry(
        entry_id=entry_id,
        transaction_hash=f"transaction-{entry_id}",
        occurred_at=ENTRY_AT + timedelta(days=days),
        token_address=token,
        quote_address=QUOTE,
        token_amount=Decimal("1"),
        quote_amount=Decimal("1"),
        trade_value_usd=Decimal("10"),
    )


class FakeRepository:
    def __init__(self) -> None:
        self.entries = (trade("one", TOKEN, 0), trade("two", TOKEN_TWO, 10))
        self.contexts = {
            "one": HistoricalContext(
                entry_id="one",
                window=PreEntryWindow.before(self.entries[0].occurred_at),
                smart_trader_net_flow_usd=Decimal("100"),
                smart_trader_avg_flow_usd=Decimal("50"),
                smart_trader_wallet_count=2,
            ),
            "two": HistoricalContext(
                entry_id="two",
                window=PreEntryWindow.before(self.entries[1].occurred_at),
                smart_trader_net_flow_usd=Decimal("0"),
                smart_trader_avg_flow_usd=None,
                smart_trader_wallet_count=0,
            ),
        }
        self.outcomes = {
            "one": (
                OutcomeObservation.from_price(
                    entry_id="one",
                    horizon=OutcomeHorizon.DAYS_7,
                    entry_at=self.entries[0].occurred_at,
                    entry_price_usd=Decimal("10"),
                    as_of=self.entries[0].occurred_at + timedelta(days=8),
                    observed_at=self.entries[0].occurred_at + timedelta(days=7),
                    observed_price_usd=Decimal("12"),
                ),
            ),
            "two": (
                OutcomeObservation.from_price(
                    entry_id="two",
                    horizon=OutcomeHorizon.DAYS_7,
                    entry_at=self.entries[1].occurred_at,
                    entry_price_usd=Decimal("10"),
                    as_of=self.entries[1].occurred_at + timedelta(days=8),
                    observed_at=self.entries[1].occurred_at + timedelta(days=7),
                    observed_price_usd=Decimal("9.9"),
                ),
            ),
        }

    def list_review_entries(self, _review_id: str):
        return self.entries

    def get_historical_context(self, _review_id: str, entry_id: str):
        return self.contexts[entry_id]

    def list_outcomes(self, _review_id: str, entry_id: str):
        return self.outcomes[entry_id]


def test_four_flow_rules_are_mutually_exclusive_and_missing_is_separate() -> None:
    assert (
        classify_flow(
            coverage=ContextCoverage.OBSERVED,
            net_flow_usd=Decimal("1"),
            wallet_count=1,
        )
        is FlowPattern.NET_INFLOW
    )
    assert (
        classify_flow(
            coverage=ContextCoverage.OBSERVED,
            net_flow_usd=Decimal("-1"),
            wallet_count=1,
        )
        is FlowPattern.NET_OUTFLOW
    )
    assert (
        classify_flow(
            coverage=ContextCoverage.OBSERVED,
            net_flow_usd=Decimal("0"),
            wallet_count=0,
        )
        is FlowPattern.NO_OBSERVED_FLOW
    )
    assert (
        classify_flow(
            coverage=ContextCoverage.OBSERVED,
            net_flow_usd=Decimal("0"),
            wallet_count=2,
        )
        is FlowPattern.ACTIVE_FLAT
    )
    assert (
        classify_flow(
            coverage=ContextCoverage.UNAVAILABLE,
            net_flow_usd=None,
            wallet_count=None,
        )
        is FlowPattern.UNAVAILABLE
    )


def test_outcome_band_is_fixed_at_two_percent() -> None:
    entry = trade("band", TOKEN, 0)

    def outcome(price: str) -> OutcomeObservation:
        return OutcomeObservation.from_price(
            entry_id=entry.entry_id,
            horizon=OutcomeHorizon.HOURS_24,
            entry_at=entry.occurred_at,
            entry_price_usd=Decimal("10"),
            as_of=entry.occurred_at + timedelta(days=2),
            observed_at=entry.occurred_at + timedelta(days=1),
            observed_price_usd=Decimal(price),
        )

    assert classify_outcome(outcome("10.2")) is OutcomeBand.FLAT
    assert classify_outcome(outcome("9.8")) is OutcomeBand.FLAT
    assert classify_outcome(outcome("10.21")) is OutcomeBand.GAIN
    assert classify_outcome(outcome("9.79")) is OutcomeBand.DECLINE
    assert classify_outcome(None) is OutcomeBand.UNAVAILABLE


def test_report_shows_rule_samples_and_same_wallet_baseline() -> None:
    report = build_precedent_report(FakeRepository(), "review", OutcomeHorizon.DAYS_7)
    inflow = next(item for item in report.patterns if item.pattern is FlowPattern.NET_INFLOW)
    inactive = next(
        item for item in report.patterns if item.pattern is FlowPattern.NO_OBSERVED_FLOW
    )
    assert inflow.sample_count == 1
    assert inflow.outcome_counts.gain == 1
    assert inactive.outcome_counts.flat == 1
    assert report.baseline.gain == 1
    assert report.baseline.flat == 1
    assert report.evaluation_status == "not_run_no_predictive_claim"


def test_preflight_missing_feature_is_not_silently_a_non_match() -> None:
    report = build_precedent_report(FakeRepository(), "review", OutcomeHorizon.DAYS_7)
    current = CurrentContext(
        token_address=TOKEN,
        observed_at=datetime(2026, 9, 17, tzinfo=UTC),
        timeframe="1d",
        coverage=ContextCoverage.UNAVAILABLE,
        smart_trader_net_flow_usd=None,
        smart_trader_avg_flow_usd=None,
        smart_trader_wallet_count=None,
    )
    comparison = compare_current_context(current, report)
    assert comparison.pattern is FlowPattern.UNAVAILABLE
    assert comparison.comparable is False
    assert comparison.missing_features == (
        "smart_trader_net_flow_usd",
        "smart_trader_wallet_count",
    )
