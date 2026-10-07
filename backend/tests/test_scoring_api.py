from uuid import UUID

from fastapi.testclient import TestClient

from app.analytics.scoring.engine import ScoredCell, ScoringError, ScoringResult
from app.api.routes.analysis import get_scoring_service
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


def test_normalization_api_exposes_twelve_public_profiles(client: TestClient) -> None:
    response = client.get("/api/analysis/scoring/normalizations")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 12
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
