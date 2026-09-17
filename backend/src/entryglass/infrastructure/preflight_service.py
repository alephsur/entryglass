"""Local background runner for one-request current-context preflights."""

import threading
from datetime import UTC, datetime

from entryglass.application.preflight import RunTokenPreflight
from entryglass.core.config import Settings
from entryglass.domain.preflight import PreflightJob, PreflightStatus
from entryglass.infrastructure.nansen.current import NansenCurrentContextClient
from entryglass.infrastructure.storage import SqliteIngestionRepository


class PreflightService:
    def __init__(self, settings: Settings, repository: SqliteIngestionRepository) -> None:
        self._settings = settings
        self._repository = repository

    @property
    def provider_configured(self) -> bool:
        return self._settings.nansen_api_key is not None

    def create(self, review_id: str, token_address: str, horizon: str) -> PreflightJob:
        if self._settings.nansen_api_key is None:
            raise RuntimeError("provider_not_configured")
        job = self._repository.create_preflight(
            review_id,
            token_address,
            horizon,
            now=datetime.now(UTC),
        )
        threading.Thread(
            target=self._run,
            args=(job.preflight_id, token_address),
            name=f"entryglass-preflight-{job.preflight_id[:8]}",
            daemon=True,
        ).start()
        return job

    def _run(self, preflight_id: str, token_address: str) -> None:
        api_key = self._settings.nansen_api_key
        if api_key is None:
            return
        try:
            with NansenCurrentContextClient(
                api_key=api_key,
                base_url=str(self._settings.nansen_base_url),
                timeout_seconds=self._settings.nansen_timeout_seconds,
                max_concurrency=self._settings.nansen_max_concurrency,
            ) as provider:
                RunTokenPreflight(
                    provider=provider,
                    repository=self._repository,
                ).execute(preflight_id, token_address)
        except Exception:
            current = self._repository.get_preflight(preflight_id)
            if current.status is PreflightStatus.PENDING:
                self._repository.set_preflight_running(preflight_id)
                current = self._repository.get_preflight(preflight_id)
            if current.status is PreflightStatus.RUNNING:
                self._repository.fail_preflight(
                    preflight_id,
                    error_code="internal_error",
                    requests_attempted=current.requests_attempted,
                    credits_used=current.credits_used,
                )
