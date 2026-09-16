"""Provider-validation contracts with no HTTP or framework dependencies."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Literal, Protocol


class ProviderEndpoint(StrEnum):
    """The three provider capabilities required by the first validation slice."""

    WALLET_DEX_TRADES = "wallet_dex_trades"
    HISTORICAL_FLOW = "historical_flow"
    HISTORICAL_WHO_BOUGHT_SOLD = "historical_who_bought_sold"


@dataclass(frozen=True, slots=True)
class UtcWindow:
    """A closed provider query window represented by UTC-aware timestamps."""

    from_utc: datetime
    to_utc: datetime

    def __post_init__(self) -> None:
        for value in (self.from_utc, self.to_utc):
            if value.tzinfo is None or value.utcoffset() != timedelta(0):
                raise ValueError("Provider validation windows must use UTC-aware timestamps.")
        if self.from_utc >= self.to_utc:
            raise ValueError("The validation window must end after it starts.")

    def as_provider_date_range(self) -> dict[str, str]:
        """Serialize the documented inclusive provider date range."""
        return {
            "from": self.from_utc.isoformat().replace("+00:00", "Z"),
            "to": self.to_utc.isoformat().replace("+00:00", "Z"),
        }


@dataclass(frozen=True, slots=True)
class ProviderValidationRequest:
    """One deliberately bounded provider request."""

    endpoint: ProviderEndpoint
    subject: str
    window: UtcWindow
    chain: Literal["solana"] = "solana"
    page: int = 1
    per_page: int = 1
    side: Literal["BUY", "SELL"] | None = None

    def __post_init__(self) -> None:
        if self.chain != "solana":
            raise ValueError("The first Entryglass release validates Solana only.")
        if not self.subject.strip():
            raise ValueError("A wallet or token address is required.")
        if self.page < 1:
            raise ValueError("Provider pages are one-based.")
        if not 1 <= self.per_page <= 1000:
            raise ValueError("Provider page size must be between 1 and 1000.")
        if self.endpoint is ProviderEndpoint.HISTORICAL_WHO_BOUGHT_SOLD:
            if self.side not in {"BUY", "SELL"}:
                raise ValueError("Historical trade validation requires BUY or SELL.")
        elif self.side is not None:
            raise ValueError("A buy/sell side applies only to historical trade validation.")


@dataclass(frozen=True, slots=True)
class ProviderResponseMetadata:
    """Safe response evidence; it deliberately excludes provider row values."""

    endpoint: ProviderEndpoint
    path: str
    status_code: int
    latency_ms: int
    record_count: int
    response_fields: tuple[str, ...]
    warning_count: int
    page: int | None
    per_page: int | None
    is_last_page: bool | None
    request_id: str | None
    quoted_credits: str | None
    used_credits: str | None
    remaining_credits: str | None
    rate_limit_remaining: str | None
    request_fingerprint: str
    response_hash: str


class ProviderValidationPort(Protocol):
    """Application boundary implemented by the Nansen adapter."""

    def validate(self, request: ProviderValidationRequest) -> ProviderResponseMetadata:
        """Execute one request and return only redacted validation metadata."""
