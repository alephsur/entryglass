"""Exercise the Nansen adapter with synthetic responses and no network."""

import json
from datetime import UTC, datetime

import httpx
import pytest
from pydantic import SecretStr

from entryglass.application.provider import (
    ProviderEndpoint,
    ProviderValidationRequest,
    UtcWindow,
)
from entryglass.infrastructure.nansen.client import (
    NansenClient,
    NansenContractError,
    NansenProviderError,
)


def request() -> ProviderValidationRequest:
    return ProviderValidationRequest(
        endpoint=ProviderEndpoint.WALLET_DEX_TRADES,
        subject="public-wallet",
        window=UtcWindow(
            datetime(2026, 9, 1, tzinfo=UTC),
            datetime(2026, 9, 2, tzinfo=UTC),
        ),
    )


def test_success_returns_only_redacted_metadata() -> None:
    def handler(http_request: httpx.Request) -> httpx.Response:
        assert http_request.url.path == "/api/v1/profiler/dex-trades"
        assert http_request.headers["apikey"] == "private-test-key"
        body = json.loads(http_request.content)
        assert body["address"] == "public-wallet"
        return httpx.Response(
            200,
            headers={
                "X-Request-Id": "request-123",
                "X-Nansen-Credits-Cost": "1",
                "X-Nansen-Credits-Used": "1",
                "X-Nansen-Credits-Remaining": "99",
                "X-RateLimit-Remaining": "14",
            },
            json={
                "data": [
                    {
                        "transaction_hash": "private-row-value",
                        "token_bought_address": "private-token-value",
                    }
                ],
                "pagination": {"page": 1, "per_page": 1, "is_last_page": True},
            },
        )

    with NansenClient(
        api_key=SecretStr("private-test-key"),
        base_url="https://api.nansen.test",
        transport=httpx.MockTransport(handler),
    ) as client:
        result = client.validate(request())

    assert result.record_count == 1
    assert result.response_fields == ("token_bought_address", "transaction_hash")
    assert result.request_id == "request-123"
    assert result.quoted_credits == "1"
    assert result.used_credits == "1"
    assert result.remaining_credits == "99"
    assert result.is_last_page is True
    assert len(result.request_fingerprint) == 64
    assert len(result.response_hash) == 64
    rendered = repr(result)
    assert "private-test-key" not in rendered
    assert "private-row-value" not in rendered
    assert "private-token-value" not in rendered


def test_nullable_warnings_remain_distinct_from_warning_entries() -> None:
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(200, json={"data": [], "warnings": None})
    )
    with NansenClient(
        api_key=SecretStr("private-test-key"),
        base_url="https://api.nansen.test",
        transport=transport,
    ) as client:
        result = client.validate(request())
    assert result.warning_count == 0
    assert result.record_count == 0
    assert result.page is None


def test_unexpected_success_envelope_fails_closed() -> None:
    transport = httpx.MockTransport(lambda _request: httpx.Response(200, json={"rows": []}))
    with (
        NansenClient(
            api_key=SecretStr("private-test-key"),
            base_url="https://api.nansen.test",
            transport=transport,
        ) as client,
        pytest.raises(NansenContractError, match="unexpected response envelope"),
    ):
        client.validate(request())


def test_provider_error_does_not_echo_message_or_request_values() -> None:
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(
            422,
            headers={"X-Request-Id": "request-422", "X-Nansen-Credits-Used": "0"},
            json={
                "code": "invalid_address_format",
                "message": "public-wallet was rejected and must not be echoed",
            },
        )
    )
    with (
        NansenClient(
            api_key=SecretStr("private-test-key"),
            base_url="https://api.nansen.test",
            transport=transport,
        ) as client,
        pytest.raises(NansenProviderError) as captured,
    ):
        client.validate(request())
    rendered = str(captured.value)
    assert "invalid_address_format" in rendered
    assert "request-422" in rendered
    assert "public-wallet" not in rendered
    assert "must not be echoed" not in rendered
