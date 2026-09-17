"""Exercise typed ingestion, retries, and safe failures without network access."""

import json
from datetime import UTC, datetime

import httpx
import pytest
from pydantic import SecretStr

from entryglass.application.ingestion import TradeProviderFailure, WalletTradeQuery
from entryglass.infrastructure.nansen.ingestion import NansenIngestionClient

WALLET = "11111111111111111111111111111111"
QUOTE = "So11111111111111111111111111111111111111112"
TOKEN = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
NOW = datetime(2026, 9, 2, tzinfo=UTC)


def query() -> WalletTradeQuery:
    return WalletTradeQuery(
        wallet_address=WALLET,
        from_utc=datetime(2026, 9, 1, tzinfo=UTC),
        to_utc=NOW,
        page=1,
        per_page=100,
    )


def row() -> dict[str, object]:
    return {
        "block_timestamp": "2026-09-01T12:00:00Z",
        "chain": "solana",
        "token_bought_address": TOKEN,
        "token_bought_amount": "25.5",
        "token_sold_address": QUOTE,
        "token_sold_amount": "2",
        "trade_value_usd": "2",
        "transaction_hash": "synthetic-transaction",
    }


def test_typed_page_preserves_decimal_and_safe_evidence() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["address"] == WALLET
        assert payload["pagination"] == {"page": 1, "per_page": 100}
        return httpx.Response(
            200,
            headers={
                "X-Request-Id": "request-1",
                "X-Nansen-Credits-Cost": "1",
                "X-Nansen-Credits-Used": "1",
            },
            json={
                "data": [row()],
                "pagination": {"page": 1, "per_page": 100, "is_last_page": True},
                "warnings": ["synthetic warning"],
            },
        )

    with NansenIngestionClient(
        api_key=SecretStr("private-test-key"),
        base_url="https://api.nansen.test",
        transport=httpx.MockTransport(handler),
        clock=lambda: NOW,
    ) as provider:
        page = provider.fetch_page(query(), max_attempts=1)

    assert str(page.legs[0].bought_amount) == "25.5"
    assert page.request_id == "request-1"
    assert page.used_credits == 1
    assert page.warnings == ("synthetic warning",)
    assert len(page.request_fingerprint) == 64
    assert len(page.response_hash) == 64


def test_transient_error_honors_retry_after_with_a_bound() -> None:
    attempts = 0
    delays: list[float] = []

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(
                429,
                headers={"Retry-After": "100"},
                json={"code": "rate_limited"},
            )
        return httpx.Response(
            200,
            headers={"X-Nansen-Credits-Used": "1"},
            json={
                "data": [],
                "pagination": {"page": 1, "per_page": 100, "is_last_page": True},
            },
        )

    with NansenIngestionClient(
        api_key=SecretStr("private-test-key"),
        base_url="https://api.nansen.test",
        transport=httpx.MockTransport(handler),
        sleeper=delays.append,
        max_retry_after_seconds=2,
        clock=lambda: NOW,
    ) as provider:
        page = provider.fetch_page(query(), max_attempts=2)

    assert page.attempt_count == 2
    assert delays == [2]


def test_schema_error_fails_closed_without_exposing_payload() -> None:
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(200, json={"private": "must not appear"})
    )
    with (
        NansenIngestionClient(
            api_key=SecretStr("private-test-key"),
            base_url="https://api.nansen.test",
            transport=transport,
            clock=lambda: NOW,
        ) as provider,
        pytest.raises(TradeProviderFailure) as captured,
    ):
        provider.fetch_page(query(), max_attempts=1)
    assert captured.value.code == "contract_error"
    assert "must not appear" not in str(captured.value)


def test_timeout_retries_only_within_the_attempt_ceiling() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        raise httpx.ReadTimeout("synthetic timeout", request=request)

    with (
        NansenIngestionClient(
            api_key=SecretStr("private-test-key"),
            base_url="https://api.nansen.test",
            transport=httpx.MockTransport(handler),
            clock=lambda: NOW,
        ) as provider,
        pytest.raises(TradeProviderFailure) as captured,
    ):
        provider.fetch_page(query(), max_attempts=2)
    assert attempts == 2
    assert captured.value.code == "transport_error"
    assert captured.value.attempts == 2
