"""Verify the deliberately small public HTTP surface."""

from fastapi.testclient import TestClient

from entryglass import __version__


def test_health_describes_the_private_preflight_stage(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "Entryglass API",
        "version": __version__,
        "stage": "preflight",
        "nansen_integration": "private_review_and_preflight",
    }


def test_openapi_advertises_review_journey(client: TestClient) -> None:
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert set(response.json()["paths"]) == {
        "/api/v1/health",
        "/api/v1/reviews",
        "/api/v1/reviews/{review_id}",
        "/api/v1/reviews/{review_id}/cancel",
        "/api/v1/reviews/{review_id}/entries",
        "/api/v1/reviews/{review_id}/entries/{entry_id}",
        "/api/v1/reviews/{review_id}/entries/{entry_id}/outcomes",
        "/api/v1/reviews/{review_id}/entries/{entry_id}/evidence",
        "/api/v1/reviews/{review_id}/precedents",
        "/api/v1/reviews/{review_id}/preflights",
        "/api/v1/reviews/{review_id}/preflights/{preflight_id}",
    }


def test_docs_are_available(client: TestClient) -> None:
    assert client.get("/docs").status_code == 200


def test_unimplemented_audit_is_not_a_fake_success(client: TestClient) -> None:
    assert client.post("/api/v1/audits", json={}).status_code == 404


def test_local_origin_is_allowed(client: TestClient) -> None:
    response = client.get("/api/v1/health", headers={"Origin": "http://localhost:5173"})
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_unknown_origin_is_not_allowed(client: TestClient) -> None:
    response = client.get("/api/v1/health", headers={"Origin": "https://untrusted.example"})
    assert "access-control-allow-origin" not in response.headers
