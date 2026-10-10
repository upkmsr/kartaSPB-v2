from uuid import UUID

from fastapi.testclient import TestClient

from app.analytics.explain import (
    ExplanationFactor,
    ExplanationTarget,
    ScenarioExplanation,
)
from app.analytics.scoring.engine import (
    ScoredCell,
    ScoringDistribution,
    ScoringError,
    ScoringResult,
)
from app.api.routes.analysis import get_scenario_explanation_service, get_scoring_service
from app.main import app


class FakeScoringService:
    def evaluate(
        self, grid_version: str, weights: dict[str, float], *, limit: int = 20
    ) -> ScoringResult:
        if "unknown.metric.value" in weights:
            raise ScoringError("unknown or disabled metric: unknown.metric.value")
        return ScoringResult(
            grid_version=grid_version,
            weights={key: float(value) for key, value in weights.items() if value > 0},
            scoring_signature="a" * 64,
            cell_count=36292,
            minimum=10,
            maximum=90,
            mean=50,
            top_cells=(
                ScoredCell(
                    cell_id="spb-square-200m-v1:1:2",
                    score=90,
                    district_id=UUID("00000000-0000-0000-0000-000000000001"),
                ),
            ),
        )

    def distribution(
        self, grid_version: str, weights: dict[str, float], district_ids: list[UUID]
    ) -> ScoringDistribution:
        if not district_ids:
            raise ScoringError("at least one district is required")
        return ScoringDistribution(
            grid_version=grid_version,
            scoring_signature="a" * 64,
            cell_count=100,
            p10=10,
            p25=25,
            p50=50,
            p75=75,
            p90=90,
        )


class FakeExplanationService:
    def explain(self, cell_id: str, encoded_spec: str) -> ScenarioExplanation:
        assert encoded_spec == "opaque-spec"
        return ScenarioExplanation(
            grid_version="spb-square-50m-v1",
            cell_id=cell_id,
            scoring_signature="a" * 64,
            score=82.5,
            factors=(
                ExplanationFactor(
                    metric_key="education.school.accessibility_index",
                    label="Доступность школ",
                    weight=100,
                    individual_score=82.5,
                    contribution=82.5,
                    target=ExplanationTarget(
                        object_id=UUID("00000000-0000-0000-0000-000000000002"),
                        name="Школа",
                        geometry_type="POINT",
                        distance_m=175,
                        area_m2=None,
                    ),
                ),
            ),
        )

def test_normalization_api_exposes_existing_and_smooth_profiles(client: TestClient) -> None:
    response = client.get("/api/analysis/scoring/normalizations")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 20
    assert all(set(item) == {
        "metric_key", "normalization_version", "label", "method", "points", "checksum"
    } for item in payload)
    metric_key = payload[0]["metric_key"]
    detail = client.get(f"/api/analysis/scoring/normalizations/{metric_key}")
    assert detail.status_code == 200
    assert detail.json()["metric_key"] == metric_key
    assert client.get(
        "/api/analysis/scoring/normalizations/unknown.metric.value"
    ).status_code == 404


def test_score_preview_requires_explicit_weights_and_returns_bounded_top_cells(
    client: TestClient,
) -> None:
    app.dependency_overrides[get_scoring_service] = lambda: FakeScoringService()
    try:
        response = client.post(
            "/api/analysis/scoring/evaluate",
            json={"weights": {"education.school.distance_m": 100}, "limit": 1},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["cell_count"] == 36292
        assert payload["weights"] == {"education.school.distance_m": 100.0}
        assert len(payload["top_cells"]) == 1

        rejected = client.post(
            "/api/analysis/scoring/evaluate",
            json={"weights": {"unknown.metric.value": 100}},
        )
        assert rejected.status_code == 422
        assert "unknown" in rejected.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_distribution_and_scenario_dimension_contracts(client: TestClient) -> None:
    district_id = UUID("00000000-0000-0000-0000-000000000001")
    app.dependency_overrides[get_scoring_service] = lambda: FakeScoringService()
    try:
        response = client.post(
            "/api/analysis/scoring/distribution",
            json={
                "grid_version": "spb-square-50m-v1",
                "weights": {"education.school.accessibility_index": 100},
                "district_ids": [str(district_id)],
            },
        )
        assert response.status_code == 200
        assert response.json() == {
            "grid_version": "spb-square-50m-v1",
            "scoring_signature": "a" * 64,
            "cell_count": 100,
            "p10": 10.0,
            "p25": 25.0,
            "p50": 50.0,
            "p75": 75.0,
            "p90": 90.0,
        }
    finally:
        app.dependency_overrides.clear()
    dimensions = client.get("/api/analysis/scenarios/dimensions")
    assert dimensions.status_code == 200
    payload = dimensions.json()
    assert len(payload) == 8
    assert {item["metric_key"] for item in payload} == {
        "education.kindergarten.accessibility_index",
        "education.school.accessibility_index",
        "transport.stop.accessibility_index",
        "healthcare.clinic.accessibility_index",
        "healthcare.hospital.accessibility_index",
        "healthcare.pharmacy.accessibility_index",
        "nature.park.accessibility_index",
        "nature.water.accessibility_index",
    }


def test_scenario_explanation_is_bound_to_the_active_spec(client: TestClient) -> None:
    app.dependency_overrides[get_scenario_explanation_service] = (
        lambda: FakeExplanationService()
    )
    try:
        response = client.post(
            "/api/analysis/scenarios/explain",
            json={"cell_id": "spb-square-50m-v1:1:2", "spec": "opaque-spec"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["score"] == 82.5
        assert payload["factors"][0]["target"]["name"] == "Школа"
        assert payload["factors"][0]["contribution"] == 82.5
    finally:
        app.dependency_overrides.clear()
