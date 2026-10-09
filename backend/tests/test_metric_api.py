from datetime import UTC, datetime
from uuid import UUID

from fastapi.testclient import TestClient

from app.analytics.metrics.contracts import MetricDefinition
from app.analytics.metrics.registry import MetricRegistry
from app.api.routes.analysis import get_metric_query_service, get_metric_registry
from app.data.metrics import CurrentMetricRun
from app.main import app

RUN_ID = UUID("00000000-0000-0000-0000-000000000777")


def definition() -> MetricDefinition:
    return MetricDefinition.model_validate(
        {
            "key": "test.synthetic.value",
            "definition_version": "1",
            "label": "Synthetic",
            "description": "Fixture only",
            "group": "test",
            "unit": "index",
            "value_semantics": "index",
            "preferred_direction": "context_only",
            "provider_key": "secret.provider",
            "calculation_version": "1",
            "provider_config": {"password": "must-not-leak"},
            "source_dependencies": ["secret.table"],
        }
    )


class FakeMetricQueryService:
    def __init__(self, current: CurrentMetricRun | None) -> None:
        self._current = current

    def current(self, metric_key: str, grid_version: str) -> CurrentMetricRun | None:
        return self._current


def test_empty_registry_override_is_supported(client: TestClient) -> None:
    app.dependency_overrides[get_metric_registry] = lambda: MetricRegistry([])
    try:
        assert client.get("/api/analysis/metrics").json() == []
        assert client.get("/api/analysis/metrics/missing.metric.key").status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_f8_production_registry_api_lists_existing_and_smooth_metrics(
    client: TestClient,
) -> None:
    response = client.get("/api/analysis/metrics")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 20
    keys = {item["key"] for item in payload}
    assert len({key for key in keys if key.endswith(".accessibility_index")}) == 8
    assert "education.school.distance_m" in keys
    assert "transport.stop.count_500m" in keys
    assert all("provider_key" not in item for item in payload)


def test_metric_api_hides_provider_details_and_exposes_current_run(client: TestClient) -> None:
    metric = definition()
    current = CurrentMetricRun(
        run_id=RUN_ID,
        metric_key=metric.key,
        definition_version="1",
        calculation_version="1",
        grid_version="spb-square-200m-v1",
        cell_count=3,
        min_value=-1.0,
        max_value=2.0,
        mean_value=0.5,
        values_checksum="a" * 64,
        created_at=datetime(2026, 10, 4, tzinfo=UTC),
    )
    app.dependency_overrides[get_metric_registry] = lambda: MetricRegistry([metric])
    app.dependency_overrides[get_metric_query_service] = lambda: FakeMetricQueryService(current)
    try:
        response = client.get("/api/analysis/metrics")
        assert response.status_code == 200
        payload = response.json()[0]
        assert payload["key"] == metric.key
        assert "provider_key" not in payload
        assert "provider_config" not in payload
        assert "source_dependencies" not in payload

        response = client.get(f"/api/analysis/metrics/{metric.key}/current")
        assert response.status_code == 200
        assert response.json()["run_id"] == str(RUN_ID)
    finally:
        app.dependency_overrides.clear()


def test_metric_current_without_published_run_is_404(client: TestClient) -> None:
    metric = definition()
    app.dependency_overrides[get_metric_registry] = lambda: MetricRegistry([metric])
    app.dependency_overrides[get_metric_query_service] = lambda: FakeMetricQueryService(None)
    try:
        response = client.get(f"/api/analysis/metrics/{metric.key}/current")
        assert response.status_code == 404
        assert response.json()["detail"] == "Current metric run not found"
    finally:
        app.dependency_overrides.clear()
