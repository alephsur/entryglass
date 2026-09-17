"""Verify the current Flow Intelligence contract without provider calls."""

import json
from datetime import UTC, datetime
from decimal import Decimal

import httpx
from pydantic import SecretStr

from entryglass.domain.context import ContextCoverage
from entryglass.infrastructure.nansen.current import NansenCurrentContextClient

TOKEN = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
NOW = datetime(2026, 9, 17, 12, tzinfo=UTC)


def test_current_flow_uses_one_day_and_preserves_observed_zero() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/tgm/flow-intelligence"
        assert json.loads(request.content) == {
            "chain": "solana",
            "token_address": TOKEN,
            "timeframe": "1d",
        }
        return httpx.Response(
            200,
            headers={"X-Nansen-Credits-Used": "1"},
            json={
                "data": [
                    {
                        "smart_trader_net_flow_usd": 0,
                        "smart_trader_avg_flow_usd": None,
                        "smart_trader_wallet_count": 0,
                    }
                ],
                "warnings": [],
            },
        )

    with NansenCurrentContextClient(
        api_key=SecretStr("test-key"),
        base_url="https://api.nansen.test",
        transport=httpx.MockTransport(handler),
        clock=lambda: NOW,
    ) as provider:
        fetched = provider.fetch_current_context(TOKEN, max_attempts=1)

    assert fetched.context.coverage is ContextCoverage.OBSERVED
    assert fetched.context.smart_trader_net_flow_usd == Decimal("0")
    assert fetched.context.smart_trader_wallet_count == 0
    assert fetched.evidence.requested_from_utc == datetime(2026, 9, 16, 12, tzinfo=UTC)


def test_empty_current_flow_is_unavailable() -> None:
    with NansenCurrentContextClient(
        api_key=SecretStr("test-key"),
        base_url="https://api.nansen.test",
        transport=httpx.MockTransport(lambda _request: httpx.Response(200, json={"data": []})),
        clock=lambda: NOW,
    ) as provider:
        fetched = provider.fetch_current_context(TOKEN, max_attempts=1)
    assert fetched.context.coverage is ContextCoverage.UNAVAILABLE
    assert fetched.context.smart_trader_net_flow_usd is None
