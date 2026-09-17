"""Verify the public M4 job contract without calling the provider."""

from pathlib import Path

from fastapi.testclient import TestClient

from entryglass.application.reviews import ReviewScope
from entryglass.core.config import Settings
from entryglass.domain.reviews import ReviewJob
from entryglass.infrastructure.storage import SqliteIngestionRepository
from entryglass.main import create_app

WALLET = "11111111111111111111111111111111"


class FakeReviewService:
    provider_configured = True

    def __init__(self, storage: SqliteIngestionRepository) -> None:
        self.storage = storage
        self.last_scope: ReviewScope | None = None

    def create(self, scope: ReviewScope) -> ReviewJob:
        from datetime import UTC, datetime

        self.last_scope = scope
        return self.storage.create_review(scope, now=datetime(2026, 9, 17, tzinfo=UTC))

    def cancel(self, review_id: str) -> ReviewJob:
        return self.storage.request_review_cancellation(review_id)


def test_create_poll_list_and_cancel_review_without_network(tmp_path: Path) -> None:
    settings = Settings(
        _env_file=None,
        environment="test",
        database_path=tmp_path / "review.sqlite3",
        review_max_entries=5,
        review_max_requests=15,
        review_max_credits=32,
    )
    storage = SqliteIngestionRepository(settings.database_path)
    service = FakeReviewService(storage)
    app = create_app(settings, repository=storage, review_service=service)  # type: ignore[arg-type]

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/reviews",
            json={
                "wallet_address": WALLET,
                "from_utc": "2026-08-01T00:00:00Z",
                "to_utc": "2026-09-01T00:00:00Z",
                "max_entries": 10,
                "max_requests": 100,
                "max_credits": 500,
            },
        )
        assert response.status_code == 202
        review = response.json()
        assert review["status"] == "pending"
        assert review["max_entries"] == 5
        assert review["max_requests"] == 15
        assert review["max_credits"] == 32
        review_id = review["review_id"]

        assert client.get(f"/api/v1/reviews/{review_id}").status_code == 200
        assert client.get(f"/api/v1/reviews/{review_id}/entries").json() == []
        cancelled = client.post(f"/api/v1/reviews/{review_id}/cancel")
        assert cancelled.status_code == 200
        assert cancelled.json()["cancellation_requested"] is True


def test_create_requires_server_provider_configuration(client: TestClient) -> None:
    response = client.post(
        "/api/v1/reviews",
        json={
            "wallet_address": WALLET,
            "from_utc": "2026-08-01T00:00:00Z",
            "to_utc": "2026-09-01T00:00:00Z",
        },
    )
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "provider_not_configured"


def test_unknown_review_is_404(client: TestClient) -> None:
    assert client.get("/api/v1/reviews/missing").status_code == 404
