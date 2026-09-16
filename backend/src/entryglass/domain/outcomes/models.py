"""Pure later-price observations kept separate from pre-entry context."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum


class OutcomeState(StrEnum):
    OBSERVED = "observed"
    MISSING_PRICE = "missing_price"
    PENDING = "pending"


class OutcomeHorizon(StrEnum):
    HOURS_24 = "24h"
    DAYS_7 = "7d"

    @property
    def duration(self) -> timedelta:
        return timedelta(hours=24) if self is OutcomeHorizon.HOURS_24 else timedelta(days=7)


@dataclass(frozen=True, slots=True)
class OutcomeObservation:
    """A reference-price change that must never be presented as realized PnL."""

    entry_id: str
    horizon: OutcomeHorizon
    target_at: datetime
    state: OutcomeState
    observed_at: datetime | None = None
    observed_price_usd: Decimal | None = None
    price_change_pct: Decimal | None = None

    def __post_init__(self) -> None:
        if not self.entry_id.strip():
            raise ValueError("An outcome entry identifier is required.")
        _require_utc(self.target_at, "Outcome target")
        values = (self.observed_at, self.observed_price_usd, self.price_change_pct)
        if self.state is OutcomeState.OBSERVED:
            if any(value is None for value in values):
                raise ValueError("Observed outcomes require time, price, and change values.")
            assert self.observed_at is not None
            assert self.observed_price_usd is not None
            _require_utc(self.observed_at, "Outcome observation")
            if self.observed_at < self.target_at:
                raise ValueError("An outcome price cannot precede its target horizon.")
            if self.observed_price_usd < 0:
                raise ValueError("An observed price cannot be negative.")
        elif any(value is not None for value in values):
            raise ValueError("Pending or missing outcomes cannot contain observed values.")

    @classmethod
    def from_price(
        cls,
        *,
        entry_id: str,
        horizon: OutcomeHorizon,
        entry_at: datetime,
        entry_price_usd: Decimal,
        as_of: datetime,
        observed_at: datetime | None,
        observed_price_usd: Decimal | None,
    ) -> "OutcomeObservation":
        _require_utc(entry_at, "Entry")
        _require_utc(as_of, "Observation clock")
        if observed_at is not None:
            _require_utc(observed_at, "Outcome observation")
        target = entry_at + horizon.duration
        if as_of < target:
            return cls(
                entry_id=entry_id,
                horizon=horizon,
                target_at=target,
                state=OutcomeState.PENDING,
            )
        if observed_at is None or observed_price_usd is None:
            return cls(
                entry_id=entry_id,
                horizon=horizon,
                target_at=target,
                state=OutcomeState.MISSING_PRICE,
            )
        if observed_at < target:
            raise ValueError("An outcome price cannot precede its target horizon.")
        if entry_price_usd <= 0 or observed_price_usd < 0:
            raise ValueError("Outcome price inputs must be non-negative and entry positive.")
        change = (observed_price_usd / entry_price_usd - Decimal(1)) * Decimal(100)
        return cls(
            entry_id=entry_id,
            horizon=horizon,
            target_at=target,
            state=OutcomeState.OBSERVED,
            observed_at=observed_at,
            observed_price_usd=observed_price_usd,
            price_change_pct=change,
        )


def _require_utc(value: datetime, label: str) -> None:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError(f"{label} timestamps must be UTC-aware.")
