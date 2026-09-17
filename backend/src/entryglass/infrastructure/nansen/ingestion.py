"""Credit-aware Nansen adapter for normalized wallet-trade ingestion."""

import hashlib
import json
import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from email.utils import parsedate_to_datetime
from types import TracebackType
from typing import Literal, Self

import httpx
from pydantic import BaseModel, ConfigDict, SecretStr, ValidationError, field_validator

from entryglass.application.ingestion import (
    TradeProviderFailure,
    WalletTradePage,
    WalletTradeQuery,
)
from entryglass.application.provider import (
    ProviderEndpoint,
    ProviderValidationRequest,
    UtcWindow,
)
from entryglass.domain.trades import SwapLeg
from entryglass.infrastructure.nansen.contracts import build_payload


class DexTradeRowDto(BaseModel):
    """Observed wallet DEX row fields used by the M2 normalizer."""

    model_config = ConfigDict(extra="ignore", allow_inf_nan=False)

    block_timestamp: datetime
    chain: Literal["solana"]
    token_bought_address: str
    token_bought_amount: Decimal
    token_sold_address: str
    token_sold_amount: Decimal
    trade_value_usd: Decimal
    transaction_hash: str

    @field_validator("block_timestamp")
    @classmethod
    def timestamp_must_be_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Wallet trade timestamps must be UTC-aware.")
        return value.astimezone(UTC)

    def to_domain(self) -> SwapLeg:
        return SwapLeg(
            transaction_hash=self.transaction_hash,
            occurred_at=self.block_timestamp,
            bought_address=self.token_bought_address,
            bought_amount=self.token_bought_amount,
            sold_address=self.token_sold_address,
            sold_amount=self.token_sold_amount,
            trade_value_usd=self.trade_value_usd,
        )


class DexTradePaginationDto(BaseModel):
    page: int
    per_page: int
    is_last_page: bool


class DexTradeEnvelopeDto(BaseModel):
    model_config = ConfigDict(extra="ignore")

    data: list[DexTradeRowDto]
    pagination: DexTradePaginationDto
    warnings: list[str] | None = None


class NansenIngestionClient:
    """Fetch typed pages with bounded retries and concurrency."""

    documented_credit_cost = 1
    _path = "/api/v1/profiler/dex-trades"
    _transient_statuses = frozenset({429, 500, 502, 503, 504})

    def __init__(
        self,
        *,
        api_key: SecretStr,
        base_url: str,
        timeout_seconds: float = 20.0,
        max_concurrency: int = 1,
        max_retry_after_seconds: float = 30.0,
        transport: httpx.BaseTransport | None = None,
        sleeper: Callable[[float], None] = time.sleep,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        if max_concurrency < 1 or max_retry_after_seconds < 0:
            raise ValueError("Concurrency must be positive and retry delay cannot be negative.")
        self._client = httpx.Client(
            base_url=base_url,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "apikey": api_key.get_secret_value(),
            },
            timeout=timeout_seconds,
            transport=transport,
        )
        self._semaphore = threading.BoundedSemaphore(max_concurrency)
        self._max_retry_after_seconds = max_retry_after_seconds
        self._sleeper = sleeper
        self._clock = clock

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    def fingerprint(self, query: WalletTradeQuery) -> str:
        payload = self._payload(query)
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()

    def fetch_page(self, query: WalletTradeQuery, *, max_attempts: int) -> WalletTradePage:
        if max_attempts < 1:
            raise ValueError("At least one provider attempt is required.")
        payload = self._payload(query)
        fingerprint = self.fingerprint(query)
        credits_used = 0
        credits_reported = False
        last_request_id: str | None = None

        with self._semaphore:
            for attempt in range(1, max_attempts + 1):
                try:
                    response = self._client.post(self._path, json=payload)
                except httpx.TransportError as error:
                    if attempt == max_attempts:
                        raise TradeProviderFailure(
                            "transport_error",
                            attempts=attempt,
                            used_credits=(
                                credits_used
                                if credits_reported
                                else self.documented_credit_cost * attempt
                            ),
                        ) from error
                    continue

                headers = response.headers
                last_request_id = headers.get("x-request-id")
                reported = _integer_header(headers.get("x-nansen-credits-used"))
                if reported is not None:
                    credits_reported = True
                    credits_used += reported
                if response.status_code != httpx.codes.OK:
                    if response.status_code in self._transient_statuses and attempt < max_attempts:
                        delay = _retry_delay(
                            headers.get("retry-after"),
                            now=self._clock(),
                            maximum=self._max_retry_after_seconds,
                        )
                        if delay > 0:
                            self._sleeper(delay)
                        continue
                    raise TradeProviderFailure(
                        _safe_error_code(response) or f"http_{response.status_code}",
                        attempts=attempt,
                        used_credits=(
                            credits_used
                            if credits_reported
                            else self.documented_credit_cost * attempt
                        ),
                        request_id=last_request_id,
                    )

                try:
                    envelope = DexTradeEnvelopeDto.model_validate(response.json())
                    legs = tuple(row.to_domain() for row in envelope.data)
                except (
                    ArithmeticError,
                    json.JSONDecodeError,
                    ValidationError,
                    ValueError,
                ) as error:
                    raise TradeProviderFailure(
                        "contract_error",
                        attempts=attempt,
                        used_credits=credits_used,
                        request_id=last_request_id,
                    ) from error
                if (
                    envelope.pagination.page != query.page
                    or envelope.pagination.per_page != query.per_page
                ):
                    raise TradeProviderFailure(
                        "pagination_mismatch",
                        attempts=attempt,
                        used_credits=credits_used,
                        request_id=last_request_id,
                    )
                return WalletTradePage(
                    legs=legs,
                    request_fingerprint=fingerprint,
                    response_hash=hashlib.sha256(response.content).hexdigest(),
                    retrieved_at=self._clock(),
                    page=envelope.pagination.page,
                    per_page=envelope.pagination.per_page,
                    is_last_page=envelope.pagination.is_last_page,
                    warnings=tuple(envelope.warnings or ()),
                    request_id=last_request_id,
                    quoted_credits=_integer_header(headers.get("x-nansen-credits-cost")),
                    used_credits=credits_used if credits_reported else None,
                    attempt_count=attempt,
                )

        raise AssertionError("Provider attempt loop ended unexpectedly.")

    @staticmethod
    def _payload(query: WalletTradeQuery) -> dict[str, object]:
        request = ProviderValidationRequest(
            endpoint=ProviderEndpoint.WALLET_DEX_TRADES,
            subject=query.wallet_address,
            window=UtcWindow(query.from_utc, query.to_utc),
            chain="solana",
            page=query.page,
            per_page=query.per_page,
        )
        return build_payload(request)


def _integer_header(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        parsed = int(value)
    except ValueError:
        return None
    return parsed if parsed >= 0 else None


def _retry_delay(value: str | None, *, now: datetime, maximum: float) -> float:
    if value is None:
        return 0.0
    try:
        delay = float(value)
    except ValueError:
        try:
            retry_at = parsedate_to_datetime(value)
        except (TypeError, ValueError):
            return 0.0
        if retry_at.tzinfo is None:
            retry_at = retry_at.replace(tzinfo=UTC)
        delay = (retry_at.astimezone(UTC) - now).total_seconds()
    return min(max(delay, 0.0), maximum)


def _safe_error_code(response: httpx.Response) -> str | None:
    try:
        payload = response.json()
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    code = payload.get("code")
    nested = payload.get("error")
    if not isinstance(code, str) and isinstance(nested, dict):
        code = nested.get("code")
    if not isinstance(code, str) or not code.replace("_", "").replace("-", "").isalnum():
        return None
    return code[:80]
