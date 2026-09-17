"""Pure models for normalized DEX entries and provider-independent swap legs."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Literal

_BASE58_ALPHABET = frozenset("123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz")


def validate_solana_address(value: str) -> str:
    """Validate a 32-byte base58 Solana address without changing its case."""
    if (
        not value
        or len(value) > 44
        or any(character not in _BASE58_ALPHABET for character in value)
    ):
        raise ValueError("A valid base58 Solana address is required.")
    number = 0
    for character in value:
        number = number * 58 + "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz".index(
            character
        )
    decoded = (b"\x00" * (len(value) - len(value.lstrip("1")))) + (
        number.to_bytes((number.bit_length() + 7) // 8, "big") if number else b""
    )
    if len(decoded) != 32:
        raise ValueError("A Solana address must decode to exactly 32 bytes.")
    return value


class AmbiguityReason(StrEnum):
    """Reasons why swap legs were deliberately not converted into an entry."""

    MULTIPLE_QUOTE_ASSETS = "multiple_quote_assets"
    MULTIPLE_OUTPUT_TOKENS = "multiple_output_tokens"
    DISCONNECTED_ROUTE = "disconnected_route"
    INVALID_AMOUNT = "invalid_amount"


@dataclass(frozen=True, slots=True)
class QuoteAsset:
    """A configured quote identity used to classify economic entries."""

    address: str
    symbol: str

    def __post_init__(self) -> None:
        validate_solana_address(self.address)
        if not self.symbol.strip():
            raise ValueError("A quote asset symbol is required.")


@dataclass(frozen=True, slots=True)
class SwapLeg:
    """One provider-independent DEX leg; several legs may form one entry."""

    transaction_hash: str
    occurred_at: datetime
    bought_address: str
    bought_amount: Decimal
    sold_address: str
    sold_amount: Decimal
    trade_value_usd: Decimal
    chain: Literal["solana"] = "solana"

    def __post_init__(self) -> None:
        if self.chain != "solana":
            raise ValueError("The first Entryglass release supports Solana only.")
        if not self.transaction_hash.strip():
            raise ValueError("A transaction hash is required.")
        if self.occurred_at.tzinfo is None or self.occurred_at.utcoffset() != timedelta(0):
            raise ValueError("Swap timestamps must be UTC-aware.")
        validate_solana_address(self.bought_address)
        validate_solana_address(self.sold_address)
        if self.bought_amount <= 0 or self.sold_amount <= 0:
            raise ValueError("Swap amounts must be positive.")
        if self.trade_value_usd < 0:
            raise ValueError("Trade value cannot be negative.")


@dataclass(frozen=True, slots=True)
class AmbiguousTrade:
    """A transaction retained for inspection instead of being guessed."""

    transaction_hash: str
    reason: AmbiguityReason
    leg_count: int

    def __post_init__(self) -> None:
        if not self.transaction_hash.strip() or self.leg_count < 1:
            raise ValueError("An ambiguous transaction requires a hash and at least one leg.")


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
        validate_solana_address(self.token_address)
        validate_solana_address(self.quote_address)
        if self.token_amount <= 0 or self.quote_amount <= 0:
            raise ValueError("Entry token amounts must be positive.")
        if self.trade_value_usd < 0:
            raise ValueError("Entry trade value cannot be negative.")

    @property
    def unit_price_usd(self) -> Decimal:
        """Return an entry reference price, not an executable price or PnL."""
        return self.trade_value_usd / self.token_amount
