"""Local background runner for durable review jobs."""

import threading
from datetime import UTC, datetime

from entryglass.application.reviews import BuildWalletReview, ReviewScope
from entryglass.core.config import Settings
from entryglass.domain.reviews import ReviewJob, ReviewStatus
from entryglass.infrastructure.nansen.history import NansenHistoricalMarketClient
from entryglass.infrastructure.nansen.ingestion import NansenIngestionClient
from entryglass.infrastructure.storage import SqliteIngestionRepository


class ReviewService:
    """Start bounded local jobs while SQLite remains the source of truth."""

    def __init__(self, settings: Settings, repository: SqliteIngestionRepository) -> None:
        self._settings = settings
        self._repository = repository

    @property
    def provider_configured(self) -> bool:
        return self._settings.nansen_api_key is not None

    def create(self, scope: ReviewScope) -> ReviewJob:
        if self._settings.nansen_api_key is None:
            raise RuntimeError("provider_not_configured")
        job = self._repository.create_review(scope, now=datetime.now(UTC))
        thread = threading.Thread(
            target=self._run,
            args=(job.review_id, scope),
            name=f"entryglass-review-{job.review_id[:8]}",
            daemon=True,
        )
        thread.start()
        return job

    def cancel(self, review_id: str) -> ReviewJob:
        return self._repository.request_review_cancellation(review_id)

    def _run(self, review_id: str, scope: ReviewScope) -> None:
        api_key = self._settings.nansen_api_key
        if api_key is None:
            self._repository.finish_review(
                review_id,
                status=ReviewStatus.FAILED,
                error_code="provider_not_configured",
            )
            return
        try:
            with (
                NansenIngestionClient(
                    api_key=api_key,
                    base_url=str(self._settings.nansen_base_url),
                    timeout_seconds=self._settings.nansen_timeout_seconds,
                    max_concurrency=self._settings.nansen_max_concurrency,
                ) as wallet_provider,
                NansenHistoricalMarketClient(
                    api_key=api_key,
                    base_url=str(self._settings.nansen_base_url),
                    timeout_seconds=self._settings.nansen_timeout_seconds,
                    max_concurrency=self._settings.nansen_max_concurrency,
                ) as history_provider,
            ):
                BuildWalletReview(
                    wallet_provider=wallet_provider,
                    history_provider=history_provider,
                    ingestion_repository=self._repository,
                    review_repository=self._repository,
                ).execute(review_id, scope)
        except Exception:
            # Provider details and payloads must not leak through HTTP or logs.
            current = self._repository.get_review(review_id)
            if current.status in {ReviewStatus.PENDING, ReviewStatus.RUNNING}:
                self._repository.finish_review(
                    review_id,
                    status=ReviewStatus.FAILED,
                    error_code="internal_error",
                )
