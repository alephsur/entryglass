"""Typed, credit-aware Nansen adapter for M3 context and price evidence."""

import hashlib
import json
import threading
import time
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from types import TracebackType
from typing import Self

import httpx
from pydantic import BaseModel, ConfigDict, SecretStr, ValidationError, field_validator

from entryglass.application.reviews import (
    ContextFetch,
    HistoricalMarketProvider,
    HistoryProviderFailure,
    PriceCandle,
    PriceFetch,
    ProviderEvidence,
)
from entryglass.domain.context import ContextCoverage, HistoricalContext, PreEntryWindow
from entryglass.domain.trades import TradeEntry
from entryglass.infrastructure.nansen.ingestion import (
    _integer_header,
    _retry_delay,
    _safe_error_code,
)


class HistoricalFlowRowDto(BaseModel):
    """Only the temporally resolved segment fields used by Entryglass."""

    model_config = ConfigDict(extra="ignore", allow_inf_nan=False)

    smart_trader_net_flow_usd: Decimal | None = None
    smart_trader_avg_flow_usd: Decimal | None = None
    smart_trader_wallet_count: int | None = None


class HistoricalFlowEnvelopeDto(BaseModel):
    model_config = ConfigDict(extra="ignore")

    data: list[HistoricalFlowRowDto]
    warnings: list[str] | None = None


class OhlcvCandleDto(BaseModel):
    model_config = ConfigDict(extra="ignore", allow_inf_nan=False)

    interval_start: datetime
    close: Decimal | None = None

    @field_validator("interval_start")
    @classmethod
    def timestamp_must_be_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("OHLCV timestamps must be UTC-aware.")
        return value.astimezone(UTC)


class OhlcvEnvelopeDto(BaseModel):
    model_config = ConfigDict(extra="ignore")

    chain: str
    token_address: str
    timeframe: str
    data: list[OhlcvCandleDto]
    truncated: bool = False
    truncation_note: str | None = None


class NansenHistoricalMarketClient(HistoricalMarketProvider):
    """Fetch context and outcomes through separate provider request paths."""

    context_credit_cost = 5
    price_credit_cost = 1
    _context_path = "/api/v1beta1/tgm/historical-token-flow-summary"
    _price_path = "/api/v1/tgm/token-ohlcv"
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

    def fetch_context(
        self,
        entry: TradeEntry,
        window: PreEntryWindow,
        *,
        max_attempts: int,
    ) -> ContextFetch:
        if not window.is_strictly_before(entry.occurred_at):
            raise ValueError("Historical context must end strictly before the entry.")
        payload = {
            "chain": "solana",
            "token_address": entry.token_address,
            "date_range": {
                "from": _provider_time(window.from_utc),
                "to": _provider_time(window.to_utc),
            },
        }
        response, evidence = self._post(
            kind="historical_context",
            endpoint=self._context_path,
            subject=entry.token_address,
            payload=payload,
            requested_from=window.from_utc,
            requested_to=window.to_utc,
            max_attempts=max_attempts,
            documented_cost=self.context_credit_cost,
        )
        try:
            envelope = HistoricalFlowEnvelopeDto.model_validate(response.json())
        except (ArithmeticError, json.JSONDecodeError, ValidationError, ValueError) as error:
            raise _contract_failure(evidence) from error
        if len(envelope.data) > 1:
            raise _contract_failure(evidence, code="unexpected_row_count")
        warnings = tuple(envelope.warnings or ())
        if not envelope.data:
            context = HistoricalContext(
                entry_id=entry.entry_id,
                window=window,
                smart_trader_net_flow_usd=None,
                smart_trader_avg_flow_usd=None,
                smart_trader_wallet_count=None,
                warnings=warnings,
                coverage=ContextCoverage.UNAVAILABLE,
            )
        else:
            row = envelope.data[0]
            context = HistoricalContext(
                entry_id=entry.entry_id,
                window=window,
                smart_trader_net_flow_usd=row.smart_trader_net_flow_usd,
                smart_trader_avg_flow_usd=row.smart_trader_avg_flow_usd,
                smart_trader_wallet_count=row.smart_trader_wallet_count,
                warnings=warnings,
            )
        return ContextFetch(context=context, evidence=_with_warnings(evidence, warnings))

    def fetch_prices(
        self,
        entry: TradeEntry,
        *,
        from_utc: datetime,
        to_utc: datetime,
        max_attempts: int,
    ) -> PriceFetch:
        payload = {
            "chain": "solana",
            "token_address": entry.token_address,
            "date": {
                "from": _provider_time(from_utc),
                "to": _provider_time(to_utc),
            },
            "timeframe": "1h",
        }
        response, evidence = self._post(
            kind="later_price",
            endpoint=self._price_path,
            subject=entry.token_address,
            payload=payload,
            requested_from=from_utc,
            requested_to=to_utc,
            max_attempts=max_attempts,
            documented_cost=self.price_credit_cost,
        )
        try:
            envelope = OhlcvEnvelopeDto.model_validate(response.json())
        except (ArithmeticError, json.JSONDecodeError, ValidationError, ValueError) as error:
            raise _contract_failure(evidence) from error
        if (
            envelope.chain != "solana"
            or envelope.token_address != entry.token_address
            or envelope.timeframe != "1h"
        ):
            raise _contract_failure(evidence, code="response_scope_mismatch")
        candles = tuple(
            PriceCandle(interval_start=item.interval_start, close=item.close)
            for item in sorted(envelope.data, key=lambda item: item.interval_start)
        )
        return PriceFetch(
            candles=candles,
            evidence=replace(
                evidence,
                truncated=envelope.truncated,
                truncation_note=envelope.truncation_note,
            ),
        )

    def _post(
        self,
        *,
        kind: str,
        endpoint: str,
        subject: str,
        payload: dict[str, object],
        requested_from: datetime,
        requested_to: datetime,
        max_attempts: int,
        documented_cost: int,
    ) -> tuple[httpx.Response, ProviderEvidence]:
        if max_attempts < 1:
            raise ValueError("At least one provider attempt is required.")
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        fingerprint = hashlib.sha256(encoded).hexdigest()
        credits_used = 0
        credits_reported = False
        request_id: str | None = None
        with self._semaphore:
            for attempt in range(1, max_attempts + 1):
                try:
                    response = self._client.post(endpoint, json=payload)
                except httpx.TransportError as error:
                    if attempt == max_attempts:
                        raise HistoryProviderFailure(
                            "transport_error",
                            attempts=attempt,
                            used_credits=(
                                credits_used if credits_reported else documented_cost * attempt
                            ),
                        ) from error
                    continue
                request_id = response.headers.get("x-request-id")
                reported = _integer_header(response.headers.get("x-nansen-credits-used"))
                if reported is not None:
                    credits_reported = True
                    credits_used += reported
                if response.status_code != httpx.codes.OK:
                    if response.status_code in self._transient_statuses and attempt < max_attempts:
                        delay = _retry_delay(
                            response.headers.get("retry-after"),
                            now=self._clock(),
                            maximum=self._max_retry_after_seconds,
                        )
                        if delay:
                            self._sleeper(delay)
                        continue
                    raise HistoryProviderFailure(
                        _safe_error_code(response) or f"http_{response.status_code}",
                        attempts=attempt,
                        used_credits=(
                            credits_used if credits_reported else documented_cost * attempt
                        ),
                        request_id=request_id,
                    )
                evidence = ProviderEvidence(
                    kind=kind,
                    endpoint=endpoint,
                    subject_hash=hashlib.sha256(subject.encode()).hexdigest(),
                    request_fingerprint=fingerprint,
                    response_hash=hashlib.sha256(response.content).hexdigest(),
                    requested_from_utc=requested_from,
                    requested_to_utc=requested_to,
                    retrieved_at=self._clock(),
                    request_id=request_id,
                    warnings=(),
                    quoted_credits=_integer_header(response.headers.get("x-nansen-credits-cost")),
                    used_credits=credits_used if credits_reported else None,
                    attempt_count=attempt,
                )
                return response, evidence
        raise AssertionError("Provider attempt loop ended unexpectedly.")


def _provider_time(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Provider timestamps must be timezone-aware.")
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _contract_failure(
    evidence: ProviderEvidence, *, code: str = "contract_error"
) -> HistoryProviderFailure:
    return HistoryProviderFailure(
        code,
        attempts=evidence.attempt_count,
        used_credits=evidence.used_credits or 0,
        request_id=evidence.request_id,
    )


def _with_warnings(evidence: ProviderEvidence, warnings: tuple[str, ...]) -> ProviderEvidence:
    return replace(evidence, warnings=warnings)
