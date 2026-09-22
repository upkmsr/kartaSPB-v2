from fastapi.testclient import TestClient

from app.api.routes.health import get_readiness_report
from app.db.health import ComponentStatus, ReadinessReport
from app.main import app


def test_live(client: TestClient) -> None:
    response = client.get("/api/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "live"}


def test_ready_returns_component_state(client: TestClient) -> None:
    report = ReadinessReport(
        status="ready",
        database=ComponentStatus(status="ready"),
        postgis=ComponentStatus(status="ready", detail="3.5.0"),
        migrations=ComponentStatus(status="ready", detail="20260922_0001"),
    )
    app.dependency_overrides[get_readiness_report] = lambda: report
    try:
        response = client.get("/api/health/ready")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["status"] == "ready"


def test_ready_returns_503_when_dependency_is_unavailable(client: TestClient) -> None:
    unavailable = ComponentStatus(status="unavailable")
    report = ReadinessReport(
        status="not_ready",
        database=unavailable,
        postgis=unavailable,
        migrations=unavailable,
    )
    app.dependency_overrides[get_readiness_report] = lambda: report
    try:
        response = client.get("/api/health/ready")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"
