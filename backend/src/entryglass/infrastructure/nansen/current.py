"""Typed Nansen Flow Intelligence adapter for the M5 current comparison."""

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import httpx
from pydantic import SecretStr, ValidationError

from entryglass.application.preflight import CurrentContextFetch, CurrentContextProvider
from entryglass.domain.context import ContextCoverage
from entryglass.domain.preflight import CurrentContext
from entryglass.domain.trades import validate_solana_address
from entryglass.infrastructure.nansen.history import (
    HistoricalFlowEnvelopeDto,
    NansenHistoricalMarketClient,
    _contract_failure,
)


class NansenCurrentContextClient(NansenHistoricalMarketClient, CurrentContextProvider):
    """Retrieve one rolling 1d Smart Trader flow summary."""

    documented_credit_cost = 1
    _current_path = "/api/v1/tgm/flow-intelligence"

    def __init__(
        self,
        *,
        api_key: SecretStr,
        base_url: str,
        timeout_seconds: float = 20.0,
        max_concurrency: int = 1,
        max_retry_after_seconds: float = 30.0,
        transport: httpx.BaseTransport | None = None,
        clock=lambda: datetime.now(UTC),
    ) -> None:
        self._current_clock = clock
        super().__init__(
            api_key=api_key,
            base_url=base_url,
            timeout_seconds=timeout_seconds,
            max_concurrency=max_concurrency,
            max_retry_after_seconds=max_retry_after_seconds,
            transport=transport,
            clock=clock,
        )

    def fetch_current_context(
        self, token_address: str, *, max_attempts: int
    ) -> CurrentContextFetch:
        validate_solana_address(token_address)
        requested_to = self._current_clock()
        requested_from = requested_to - timedelta(days=1)
        response, evidence = self._post(
            kind="current_context",
            endpoint=self._current_path,
            subject=token_address,
            payload={
                "chain": "solana",
                "token_address": token_address,
                "timeframe": "1d",
            },
            requested_from=requested_from,
            requested_to=requested_to,
            max_attempts=max_attempts,
            documented_cost=self.documented_credit_cost,
        )
        try:
            envelope = HistoricalFlowEnvelopeDto.model_validate(response.json())
        except (ArithmeticError, json.JSONDecodeError, ValidationError, ValueError) as error:
            raise _contract_failure(evidence) from error
        if len(envelope.data) > 1:
            raise _contract_failure(evidence, code="unexpected_row_count")
        warnings = tuple(envelope.warnings or ())
        if not envelope.data:
            context = CurrentContext(
                token_address=token_address,
                observed_at=evidence.retrieved_at,
                timeframe="1d",
                coverage=ContextCoverage.UNAVAILABLE,
                smart_trader_net_flow_usd=None,
                smart_trader_avg_flow_usd=None,
                smart_trader_wallet_count=None,
                warnings=warnings,
            )
        else:
            row = envelope.data[0]
            context = CurrentContext(
                token_address=token_address,
                observed_at=evidence.retrieved_at,
                timeframe="1d",
                coverage=ContextCoverage.OBSERVED,
                smart_trader_net_flow_usd=row.smart_trader_net_flow_usd,
                smart_trader_avg_flow_usd=row.smart_trader_avg_flow_usd,
                smart_trader_wallet_count=row.smart_trader_wallet_count,
                warnings=warnings,
            )
        return CurrentContextFetch(
            context=context,
            evidence=replace(evidence, warnings=warnings),
        )
