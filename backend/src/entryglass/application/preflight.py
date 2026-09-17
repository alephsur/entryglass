"""One bounded current-context request for a durable token preflight."""

from dataclasses import dataclass
from typing import Protocol

from entryglass.application.reviews import HistoryProviderFailure, ProviderEvidence
from entryglass.domain.preflight import CurrentContext, PreflightJob


@dataclass(frozen=True, slots=True)
class CurrentContextFetch:
    context: CurrentContext
    evidence: ProviderEvidence


class CurrentContextProvider(Protocol):
    documented_credit_cost: int

    def fetch_current_context(
        self, token_address: str, *, max_attempts: int
    ) -> CurrentContextFetch: ...


class PreflightRepository(Protocol):
    def set_preflight_running(self, preflight_id: str) -> None: ...

    def complete_preflight(
        self,
        preflight_id: str,
        *,
        context: CurrentContext,
        evidence: ProviderEvidence,
        requests_attempted: int,
        credits_used: int,
    ) -> PreflightJob: ...

    def fail_preflight(
        self,
        preflight_id: str,
        *,
        error_code: str,
        requests_attempted: int,
        credits_used: int,
    ) -> PreflightJob: ...


class RunTokenPreflight:
    def __init__(
        self,
        *,
        provider: CurrentContextProvider,
        repository: PreflightRepository,
        max_attempts: int = 2,
    ) -> None:
        self._provider = provider
        self._repository = repository
        self._max_attempts = max_attempts

    def execute(self, preflight_id: str, token_address: str) -> PreflightJob:
        self._repository.set_preflight_running(preflight_id)
        try:
            fetched = self._provider.fetch_current_context(
                token_address, max_attempts=self._max_attempts
            )
        except HistoryProviderFailure as error:
            return self._repository.fail_preflight(
                preflight_id,
                error_code=error.code,
                requests_attempted=error.attempts,
                credits_used=error.used_credits,
            )
        credits = (
            fetched.evidence.used_credits
            if fetched.evidence.used_credits is not None
            else self._provider.documented_credit_cost * fetched.evidence.attempt_count
        )
        return self._repository.complete_preflight(
            preflight_id,
            context=fetched.context,
            evidence=fetched.evidence,
            requests_attempted=fetched.evidence.attempt_count,
            credits_used=credits,
        )
