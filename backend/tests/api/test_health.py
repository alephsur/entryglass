"""Verify the small public surface of the scaffold."""

from fastapi.testclient import TestClient

from entryglass import __version__


def test_health_is_explicit_about_unimplemented_features(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "Entryglass API",
        "version": __version__,
        "stage": "scaffold",
        "nansen_integration": "validation_only",
    }


def test_openapi_only_advertises_health(client: TestClient) -> None:
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert set(response.json()["paths"]) == {"/api/v1/health"}


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
