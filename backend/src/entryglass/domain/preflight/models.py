"""Pure current-context and durable preflight job state."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum

from entryglass.domain.context import ContextCoverage
from entryglass.domain.trades import validate_solana_address


class PreflightStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class CurrentContext:
    token_address: str
    observed_at: datetime
    timeframe: str
    coverage: ContextCoverage
    smart_trader_net_flow_usd: Decimal | None
    smart_trader_avg_flow_usd: Decimal | None
    smart_trader_wallet_count: int | None
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        validate_solana_address(self.token_address)
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() != timedelta(0):
            raise ValueError("Current-context timestamps must be UTC-aware.")
        if self.timeframe != "1d":
            raise ValueError("M5 compares only the documented one-day current timeframe.")
        values = (
            self.smart_trader_net_flow_usd,
            self.smart_trader_avg_flow_usd,
            self.smart_trader_wallet_count,
        )
        if self.coverage is ContextCoverage.UNAVAILABLE and any(
            value is not None for value in values
        ):
            raise ValueError("Unavailable current context cannot contain observations.")
        if self.smart_trader_wallet_count is not None and self.smart_trader_wallet_count < 0:
            raise ValueError("A wallet count cannot be negative.")


@dataclass(frozen=True, slots=True)
class PreflightJob:
    preflight_id: str
    review_id: str
    token_address: str
    horizon: str
    status: PreflightStatus
    created_at: datetime
    updated_at: datetime
    requests_attempted: int = 0
    credits_used: int = 0
    error_code: str | None = None
    context: CurrentContext | None = None

    def __post_init__(self) -> None:
        if not self.preflight_id.strip() or not self.review_id.strip():
            raise ValueError("Preflight identifiers are required.")
        validate_solana_address(self.token_address)
        if self.horizon not in {"24h", "7d"}:
            raise ValueError("Preflight horizon must be 24h or 7d.")
        for value in (self.created_at, self.updated_at):
            if value.tzinfo is None or value.utcoffset() != timedelta(0):
                raise ValueError("Preflight timestamps must be UTC-aware.")
        if self.requests_attempted < 0 or self.credits_used < 0:
            raise ValueError("Preflight accounting cannot be negative.")
        if self.status is PreflightStatus.COMPLETE and self.context is None:
            raise ValueError("A complete preflight requires current context.")
