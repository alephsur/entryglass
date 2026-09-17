"""Exercise M3 provider contracts without credentials or network access."""

import json
from datetime import UTC, datetime
from decimal import Decimal

import httpx
import pytest
from pydantic import SecretStr

from entryglass.application.reviews import HistoryProviderFailure
from entryglass.domain.context import ContextCoverage, PreEntryWindow
from entryglass.domain.trades import TradeEntry
from entryglass.infrastructure.nansen.history import NansenHistoricalMarketClient

TOKEN = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
QUOTE = "So11111111111111111111111111111111111111112"
NOW = datetime(2026, 9, 17, 12, tzinfo=UTC)


def entry() -> TradeEntry:
    return TradeEntry(
        entry_id="entry-1",
        transaction_hash="transaction-1",
        occurred_at=datetime(2026, 9, 10, 12, tzinfo=UTC),
        token_address=TOKEN,
        quote_address=QUOTE,
        token_amount=Decimal("2"),
        quote_amount=Decimal("1"),
        trade_value_usd=Decimal("4"),
    )


def test_context_request_ends_one_second_before_entry_and_preserves_zero() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert request.url.path.endswith("historical-token-flow-summary")
        assert payload["date_range"]["to"] == "2026-09-10T11:59:59Z"
        return httpx.Response(
            200,
            headers={"X-Nansen-Credits-Used": "5", "X-Request-Id": "context-1"},
            json={
                "data": [
                    {
                        "smart_trader_net_flow_usd": 0,
                        "smart_trader_avg_flow_usd": None,
                        "smart_trader_wallet_count": 0,
                    }
                ],
                "warnings": ["synthetic warning"],
            },
        )

    with NansenHistoricalMarketClient(
        api_key=SecretStr("test-key"),
        base_url="https://api.nansen.test",
        transport=httpx.MockTransport(handler),
        clock=lambda: NOW,
    ) as provider:
        result = provider.fetch_context(
            entry(), PreEntryWindow.before(entry().occurred_at), max_attempts=1
        )

    assert result.context.coverage is ContextCoverage.OBSERVED
    assert result.context.smart_trader_net_flow_usd == Decimal("0")
    assert result.context.smart_trader_avg_flow_usd is None
    assert result.context.warnings == ("synthetic warning",)
    assert result.evidence.used_credits == 5


def test_empty_context_is_unavailable_not_zero() -> None:
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(200, json={"data": [], "warnings": []})
    )
    with NansenHistoricalMarketClient(
        api_key=SecretStr("test-key"),
        base_url="https://api.nansen.test",
        transport=transport,
        clock=lambda: NOW,
    ) as provider:
        result = provider.fetch_context(
            entry(), PreEntryWindow.before(entry().occurred_at), max_attempts=1
        )
    assert result.context.coverage is ContextCoverage.UNAVAILABLE
    assert result.context.smart_trader_net_flow_usd is None


def test_ohlcv_uses_supported_date_contract_and_rejects_scope_mismatch() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert "date" in payload
        assert "date_range" not in payload
        return httpx.Response(
            200,
            json={
                "chain": "solana",
                "token_address": "wrong-token",
                "timeframe": "1h",
                "data": [],
            },
        )

    with (
        NansenHistoricalMarketClient(
            api_key=SecretStr("test-key"),
            base_url="https://api.nansen.test",
            transport=httpx.MockTransport(handler),
            clock=lambda: NOW,
        ) as provider,
        pytest.raises(HistoryProviderFailure) as captured,
    ):
        provider.fetch_prices(
            entry(),
            from_utc=datetime(2026, 9, 11, 12, tzinfo=UTC),
            to_utc=datetime(2026, 9, 11, 14, tzinfo=UTC),
            max_attempts=1,
        )
    assert captured.value.code == "response_scope_mismatch"
