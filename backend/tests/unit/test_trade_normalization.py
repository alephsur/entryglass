"""Verify M2 address and economic-entry normalization rules."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from entryglass.domain.trades import (
    AmbiguityReason,
    QuoteAsset,
    SwapLeg,
    normalize_trade_legs,
    validate_solana_address,
)

WALLET = "11111111111111111111111111111111"
QUOTE = "So11111111111111111111111111111111111111112"
TOKEN = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
TOKEN_TWO = "metaqbxxUerdq28cj1RbAWkYQm3ybzjb6a8bt518x1s"
AT = datetime(2026, 9, 1, 12, tzinfo=UTC)


def leg(
    transaction: str,
    sold: str,
    bought: str,
    sold_amount: str,
    bought_amount: str,
    value: str,
) -> SwapLeg:
    return SwapLeg(
        transaction_hash=transaction,
        occurred_at=AT,
        bought_address=bought,
        bought_amount=Decimal(bought_amount),
        sold_address=sold,
        sold_amount=Decimal(sold_amount),
        trade_value_usd=Decimal(value),
    )


def test_solana_validation_preserves_case_and_rejects_invalid_input() -> None:
    assert validate_solana_address(TOKEN) == TOKEN
    with pytest.raises(ValueError, match="base58"):
        validate_solana_address("not-a-solana-address")
    with pytest.raises(ValueError, match="32 bytes"):
        validate_solana_address("1111")


def test_routed_and_duplicate_legs_become_one_economic_entry() -> None:
    legs = (
        leg("tx-route", QUOTE, TOKEN_TWO, "2", "4", "2"),
        leg("tx-route", TOKEN_TWO, TOKEN, "4", "20", "2"),
        leg("tx-route", TOKEN_TWO, TOKEN, "4", "20", "2"),
    )

    result = normalize_trade_legs(legs, (QuoteAsset(QUOTE, "SOL"),))

    assert len(result.entries) == 1
    assert result.entries[0].quote_amount == Decimal("2")
    assert result.entries[0].token_amount == Decimal("20")
    assert result.entries[0].token_address == TOKEN
    assert result.ambiguous == ()


def test_exit_and_quote_to_quote_activity_are_not_entries() -> None:
    result = normalize_trade_legs(
        (
            leg("tx-exit", TOKEN, QUOTE, "10", "1", "1"),
            leg("tx-quote", QUOTE, QUOTE, "1", "1", "1"),
            leg("tx-no-quote", TOKEN_TWO, TOKEN, "5", "10", "1"),
        ),
        (QuoteAsset(QUOTE, "SOL"),),
    )
    assert result.entries == ()


def test_multiple_outputs_are_preserved_as_ambiguous() -> None:
    result = normalize_trade_legs(
        (
            leg("tx-ambiguous", QUOTE, TOKEN, "1", "10", "1"),
            leg("tx-ambiguous", QUOTE, TOKEN_TWO, "1", "5", "1"),
        ),
        (QuoteAsset(QUOTE, "SOL"),),
    )
    assert result.entries == ()
    assert result.ambiguous[0].reason is AmbiguityReason.MULTIPLE_OUTPUT_TOKENS
