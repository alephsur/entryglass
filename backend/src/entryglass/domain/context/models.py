"""Pure pre-entry context models and temporal-boundary rules."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum


class ObservationState(StrEnum):
    """Distinguish observed values from unavailable provider fields."""

    OBSERVED = "observed"
    UNAVAILABLE = "unavailable"


class ContextCoverage(StrEnum):
    """Overall availability of one strictly pre-entry context."""

    OBSERVED = "observed"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class PreEntryWindow:
    """A closed provider window that ends strictly before an entry."""

    from_utc: datetime
    to_utc: datetime

    @classmethod
    def before(
        cls,
        entry_at: datetime,
        *,
        lookback: timedelta = timedelta(hours=24),
        exclusion: timedelta = timedelta(seconds=1),
    ) -> "PreEntryWindow":
        if entry_at.tzinfo is None or entry_at.utcoffset() != timedelta(0):
            raise ValueError("Entry timestamps must be UTC-aware.")
        if lookback <= timedelta(0) or exclusion <= timedelta(0):
            raise ValueError("Lookback and exclusion intervals must be positive.")
        cutoff = entry_at - exclusion
        return cls(from_utc=cutoff - lookback, to_utc=cutoff)

    def __post_init__(self) -> None:
        for value in (self.from_utc, self.to_utc):
            if value.tzinfo is None or value.utcoffset() != timedelta(0):
                raise ValueError("Context windows must use UTC-aware timestamps.")
        if self.from_utc >= self.to_utc:
            raise ValueError("Context windows must have positive duration.")

    def is_strictly_before(self, entry_at: datetime) -> bool:
        """Return whether the inclusive provider upper bound precedes the entry."""
        return self.to_utc < entry_at


@dataclass(frozen=True, slots=True)
class HistoricalContext:
    """Historical Smart Trader observations for one pre-entry window."""

    entry_id: str
    window: PreEntryWindow
    smart_trader_net_flow_usd: Decimal | None
    smart_trader_avg_flow_usd: Decimal | None
    smart_trader_wallet_count: int | None
    warnings: tuple[str, ...] = ()
    coverage: ContextCoverage = ContextCoverage.OBSERVED

    def __post_init__(self) -> None:
        if not self.entry_id.strip():
            raise ValueError("A context entry identifier is required.")
        if self.smart_trader_wallet_count is not None and self.smart_trader_wallet_count < 0:
            raise ValueError("A wallet count cannot be negative.")
        values = (
            self.smart_trader_net_flow_usd,
            self.smart_trader_avg_flow_usd,
            self.smart_trader_wallet_count,
        )
        if self.coverage is ContextCoverage.UNAVAILABLE and any(
            value is not None for value in values
        ):
            raise ValueError("Unavailable context cannot contain observed segment values.")

    @property
    def net_flow_state(self) -> ObservationState:
        return (
            ObservationState.UNAVAILABLE
            if self.smart_trader_net_flow_usd is None
            else ObservationState.OBSERVED
        )

    @property
    def average_flow_state(self) -> ObservationState:
        return (
            ObservationState.UNAVAILABLE
            if self.smart_trader_avg_flow_usd is None
            else ObservationState.OBSERVED
        )
