"""Verify the documented provider request contracts without network calls."""

from datetime import UTC, datetime

import pytest

from entryglass.application.provider import (
    ProviderEndpoint,
    ProviderValidationRequest,
    UtcWindow,
)
from entryglass.infrastructure.nansen.contracts import HistoricalLabel, build_payload


def window() -> UtcWindow:
    return UtcWindow(
        datetime(2026, 9, 1, tzinfo=UTC),
        datetime(2026, 9, 2, tzinfo=UTC),
    )


def test_window_requires_utc_aware_timestamps() -> None:
    with pytest.raises(ValueError, match="UTC-aware"):
        UtcWindow(datetime(2026, 9, 1), datetime(2026, 9, 2))


def test_window_requires_a_positive_interval() -> None:
    instant = datetime(2026, 9, 1, tzinfo=UTC)
    with pytest.raises(ValueError, match="end after"):
        UtcWindow(instant, instant)


def test_wallet_dex_trade_payload_matches_current_schema() -> None:
    request = ProviderValidationRequest(
        endpoint=ProviderEndpoint.WALLET_DEX_TRADES,
        subject="public-wallet",
        window=window(),
    )
    assert build_payload(request) == {
        "address": "public-wallet",
        "chain": "solana",
        "date": {"from": "2026-09-01T00:00:00Z", "to": "2026-09-02T00:00:00Z"},
        "pagination": {"page": 1, "per_page": 1},
        "order_by": [{"field": "block_timestamp", "direction": "DESC"}],
    }


def test_historical_flow_payload_preserves_explicit_date_range() -> None:
    request = ProviderValidationRequest(
        endpoint=ProviderEndpoint.HISTORICAL_FLOW,
        subject="public-token",
        window=window(),
    )
    assert build_payload(request) == {
        "chain": "solana",
        "token_address": "public-token",
        "date_range": {
            "from": "2026-09-01T00:00:00Z",
            "to": "2026-09-02T00:00:00Z",
        },
        "apply_blacklist_filter": True,
    }


def test_historical_trade_payload_keeps_buy_and_sell_explicit() -> None:
    request = ProviderValidationRequest(
        endpoint=ProviderEndpoint.HISTORICAL_WHO_BOUGHT_SOLD,
        subject="public-token",
        window=window(),
        side="SELL",
    )
    payload = build_payload(request)
    assert payload["buy_or_sell"] == "SELL"
    assert payload["order_by"] == [{"field": "sold_volume_usd", "direction": "DESC"}]
    assert payload["pagination"] == {"page": 1, "per_page": 1}
    assert payload["filters"] == {"include_labels": ["Smart Trader"]}


def test_historical_labels_remain_distinct() -> None:
    assert HistoricalLabel.SMART_TRADER != HistoricalLabel.SMART_TRADER_30D
    assert HistoricalLabel.SMART_TRADER != HistoricalLabel.SMART_DEX_TRADER
    assert len({label.value for label in HistoricalLabel}) == 8


def test_side_is_rejected_for_non_trade_endpoint() -> None:
    with pytest.raises(ValueError, match="applies only"):
        ProviderValidationRequest(
            endpoint=ProviderEndpoint.HISTORICAL_FLOW,
            subject="public-token",
            window=window(),
            side="BUY",
        )
