"""Deterministic conversion from DEX legs to economic wallet entries."""

import hashlib
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal

from entryglass.domain.trades.models import (
    AmbiguityReason,
    AmbiguousTrade,
    QuoteAsset,
    SwapLeg,
    TradeEntry,
)


@dataclass(frozen=True, slots=True)
class NormalizationResult:
    entries: tuple[TradeEntry, ...]
    ambiguous: tuple[AmbiguousTrade, ...]


def normalize_trade_legs(
    legs: tuple[SwapLeg, ...],
    quote_assets: tuple[QuoteAsset, ...],
) -> NormalizationResult:
    """Group routed and duplicate legs without treating exits as entries."""
    quote_addresses = {asset.address for asset in quote_assets}
    if not quote_addresses:
        raise ValueError("At least one quote asset is required.")

    by_transaction: dict[str, list[SwapLeg]] = defaultdict(list)
    seen: set[tuple[object, ...]] = set()
    for leg in legs:
        signature = (
            leg.transaction_hash,
            leg.occurred_at,
            leg.bought_address,
            leg.bought_amount,
            leg.sold_address,
            leg.sold_amount,
            leg.trade_value_usd,
        )
        if signature not in seen:
            seen.add(signature)
            by_transaction[leg.transaction_hash].append(leg)

    entries: list[TradeEntry] = []
    ambiguous: list[AmbiguousTrade] = []
    for transaction_hash, transaction_legs in by_transaction.items():
        if all(
            leg.sold_address in quote_addresses and leg.bought_address in quote_addresses
            for leg in transaction_legs
        ):
            continue
        sources = {
            leg.sold_address for leg in transaction_legs if leg.sold_address in quote_addresses
        }
        if not sources:
            continue
        if len(sources) > 1:
            ambiguous.append(
                AmbiguousTrade(
                    transaction_hash=transaction_hash,
                    reason=AmbiguityReason.MULTIPLE_QUOTE_ASSETS,
                    leg_count=len(transaction_legs),
                )
            )
            continue

        quote_address = next(iter(sources))
        reachable = _reachable_tokens(transaction_legs, quote_address)
        sinks = {
            token
            for token in reachable
            if token not in quote_addresses
            and not any(leg.sold_address == token for leg in transaction_legs)
        }
        if not sinks:
            direct_outputs = {
                leg.bought_address
                for leg in transaction_legs
                if leg.sold_address == quote_address and leg.bought_address not in quote_addresses
            }
            sinks = direct_outputs
        if len(sinks) != 1:
            ambiguous.append(
                AmbiguousTrade(
                    transaction_hash=transaction_hash,
                    reason=(
                        AmbiguityReason.MULTIPLE_OUTPUT_TOKENS
                        if len(sinks) > 1
                        else AmbiguityReason.DISCONNECTED_ROUTE
                    ),
                    leg_count=len(transaction_legs),
                )
            )
            continue

        token_address = next(iter(sinks))
        quote_amount = sum(
            (leg.sold_amount for leg in transaction_legs if leg.sold_address == quote_address),
            start=Decimal(0),
        )
        token_amount = sum(
            (leg.bought_amount for leg in transaction_legs if leg.bought_address == token_address),
            start=Decimal(0),
        )
        if quote_amount <= 0 or token_amount <= 0:
            ambiguous.append(
                AmbiguousTrade(
                    transaction_hash=transaction_hash,
                    reason=AmbiguityReason.INVALID_AMOUNT,
                    leg_count=len(transaction_legs),
                )
            )
            continue

        occurred_at = min(leg.occurred_at for leg in transaction_legs)
        trade_value_usd = max(leg.trade_value_usd for leg in transaction_legs)
        identity = f"solana:{transaction_hash}:{quote_address}:{token_address}"
        entries.append(
            TradeEntry(
                entry_id=hashlib.sha256(identity.encode()).hexdigest()[:32],
                transaction_hash=transaction_hash,
                occurred_at=occurred_at,
                token_address=token_address,
                quote_address=quote_address,
                token_amount=token_amount,
                quote_amount=quote_amount,
                trade_value_usd=trade_value_usd,
            )
        )

    entries.sort(key=lambda entry: (entry.occurred_at, entry.entry_id), reverse=True)
    ambiguous.sort(key=lambda item: item.transaction_hash)
    return NormalizationResult(entries=tuple(entries), ambiguous=tuple(ambiguous))


def _reachable_tokens(legs: list[SwapLeg], source: str) -> set[str]:
    reachable = {source}
    changed = True
    while changed:
        changed = False
        for leg in legs:
            if leg.sold_address in reachable and leg.bought_address not in reachable:
                reachable.add(leg.bought_address)
                changed = True
    return reachable
