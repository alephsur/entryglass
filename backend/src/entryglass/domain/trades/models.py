"""Pure models for normalized DEX entries."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Literal


@dataclass(frozen=True, slots=True)
class TradeEntry:
    """One normalized quote-asset-to-token DEX entry."""

    entry_id: str
    transaction_hash: str
    occurred_at: datetime
    token_address: str
    quote_address: str
    token_amount: Decimal
    quote_amount: Decimal
    trade_value_usd: Decimal
    chain: Literal["solana"] = "solana"

    def __post_init__(self) -> None:
        if self.chain != "solana":
            raise ValueError("The validated entry contract supports Solana only.")
        if self.occurred_at.tzinfo is None or self.occurred_at.utcoffset() != timedelta(0):
            raise ValueError("Entry timestamps must be UTC-aware.")
        if not all(
            value.strip()
            for value in (
                self.entry_id,
                self.transaction_hash,
                self.token_address,
                self.quote_address,
            )
        ):
            raise ValueError("Entry identifiers and token addresses are required.")
        if self.token_amount <= 0 or self.quote_amount <= 0:
            raise ValueError("Entry token amounts must be positive.")
        if self.trade_value_usd < 0:
            raise ValueError("Entry trade value cannot be negative.")

    @property
    def unit_price_usd(self) -> Decimal:
        """Return an entry reference price, not an executable price or PnL."""
        return self.trade_value_usd / self.token_amount
