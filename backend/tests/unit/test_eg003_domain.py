"""Protect the temporal and accounting boundaries validated during EG-003."""

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from entryglass.domain.context import HistoricalContext, ObservationState, PreEntryWindow
from entryglass.domain.outcomes import OutcomeHorizon, OutcomeObservation, OutcomeState
from entryglass.domain.trades import TradeEntry
from entryglass.infrastructure.nansen.contracts import ValidationEnvelope

FIXTURES = Path(__file__).parents[1] / "fixtures" / "nansen"


def entry() -> TradeEntry:
    return TradeEntry(
        entry_id="synthetic-entry",
        transaction_hash="synthetic-transaction",
        occurred_at=datetime(2026, 1, 1, 12, tzinfo=UTC),
        token_address="synthetic-token",
        quote_address="synthetic-quote",
        token_amount=Decimal("25"),
        quote_amount=Decimal("5"),
        trade_value_usd=Decimal("5"),
    )


def test_entry_uses_decimal_reference_price() -> None:
    assert entry().unit_price_usd == Decimal("0.2")


def test_context_window_excludes_the_entry_second() -> None:
    trade = entry()
    window = PreEntryWindow.before(trade.occurred_at)

    assert window.to_utc == trade.occurred_at - timedelta(seconds=1)
    assert window.from_utc == trade.occurred_at - timedelta(hours=24, seconds=1)
    assert window.is_strictly_before(trade.occurred_at)


def test_context_keeps_unavailable_distinct_from_observed_zero() -> None:
    context = HistoricalContext(
        entry_id=entry().entry_id,
        window=PreEntryWindow.before(entry().occurred_at),
        smart_trader_net_flow_usd=Decimal(0),
        smart_trader_avg_flow_usd=None,
        smart_trader_wallet_count=0,
    )

    assert context.net_flow_state is ObservationState.OBSERVED
    assert context.average_flow_state is ObservationState.UNAVAILABLE


def test_later_price_change_is_an_observation_not_pnl() -> None:
    trade = entry()
    target = trade.occurred_at + timedelta(hours=24)
    outcome = OutcomeObservation.from_price(
        entry_id=trade.entry_id,
        horizon=OutcomeHorizon.HOURS_24,
        entry_at=trade.occurred_at,
        entry_price_usd=trade.unit_price_usd,
        as_of=target + timedelta(hours=1),
        observed_at=target,
        observed_price_usd=Decimal("0.1"),
    )

    assert outcome.state is OutcomeState.OBSERVED
    assert outcome.price_change_pct == Decimal("-50.0")
    assert not hasattr(outcome, "realized_pnl")


def test_pending_and_missing_outcomes_are_different_states() -> None:
    trade = entry()
    pending = OutcomeObservation.from_price(
        entry_id=trade.entry_id,
        horizon=OutcomeHorizon.DAYS_7,
        entry_at=trade.occurred_at,
        entry_price_usd=trade.unit_price_usd,
        as_of=trade.occurred_at + timedelta(days=1),
        observed_at=None,
        observed_price_usd=None,
    )
    missing = OutcomeObservation.from_price(
        entry_id=trade.entry_id,
        horizon=OutcomeHorizon.HOURS_24,
        entry_at=trade.occurred_at,
        entry_price_usd=trade.unit_price_usd,
        as_of=trade.occurred_at + timedelta(days=2),
        observed_at=None,
        observed_price_usd=None,
    )

    assert pending.state is OutcomeState.PENDING
    assert missing.state is OutcomeState.MISSING_PRICE


def test_outcomes_reject_naive_timestamps() -> None:
    trade = entry()
    with pytest.raises(ValueError, match="UTC-aware"):
        OutcomeObservation.from_price(
            entry_id=trade.entry_id,
            horizon=OutcomeHorizon.HOURS_24,
            entry_at=datetime(2026, 1, 1, 12),
            entry_price_usd=trade.unit_price_usd,
            as_of=datetime(2026, 1, 3, 12, tzinfo=UTC),
            observed_at=None,
            observed_price_usd=None,
        )


@pytest.mark.parametrize(
    "fixture_name, expected_fields",
    [
        ("dex_trades.synthetic.json", {"transaction_hash", "token_bought_address"}),
        (
            "historical_flow.synthetic.json",
            {"smart_trader_net_flow_usd", "smart_trader_avg_flow_usd"},
        ),
        ("ohlcv.synthetic.json", {"interval_start", "close", "market_cap"}),
    ],
)
def test_hand_authored_provider_fixtures_are_valid_envelopes(
    fixture_name: str, expected_fields: set[str]
) -> None:
    payload = json.loads((FIXTURES / fixture_name).read_text())
    envelope = ValidationEnvelope.model_validate(payload)

    assert expected_fields <= envelope.data[0].keys()
