from fastapi.testclient import TestClient

from app.analytics.heatmap import (
    HEATMAP_DELIVERY_VERSION,
    HeatmapError,
    HeatmapTile,
    PreparedHeatmap,
)
from app.api.routes.analysis import get_heatmap_service
from app.main import app


class FakeHeatmapService:
    def prepare(self, grid_version: str, weights: dict[str, float]) -> PreparedHeatmap:
        if "unknown.metric" in weights:
            raise HeatmapError("unknown or disabled metric: unknown.metric")
        return PreparedHeatmap(
            grid_version=grid_version,
            weights={key: float(value) for key, value in sorted(weights.items())},
            scoring_signature="a" * 64,
            spec="opaque-spec",
            cell_count=36292,
            minimum=0,
            maximum=100,
            mean=50,
            tile_url_template=(
                f"/api/analysis/heatmap/tiles/{'a' * 64}/"
                "{z}/{x}/{y}.mvt?spec=opaque-spec"
            ),
        )

    def tile(
        self,
        scoring_signature: str,
        z: int,
        x: int,
        y: int,
        encoded_spec: str,
    ) -> HeatmapTile:
        if encoded_spec == "tampered":
            raise HeatmapError("scoring signature does not match heatmap spec")
        return HeatmapTile(
            payload=b"" if (x, y) == (0, 0) else b"mvt",
            etag="b" * 64,
            scoring_signature=scoring_signature,
        )


def test_prepare_accepts_single_and_multi_metric_explicit_weights(
    client: TestClient,
) -> None:
    app.dependency_overrides[get_heatmap_service] = lambda: FakeHeatmapService()
    try:
        for weights in (
            {"education.school.distance_m": 100},
            {
                "education.school.distance_m": 100,
                "nature.park.distance_m": 70,
            },
        ):
            response = client.post(
                "/api/analysis/heatmap/prepare", json={"weights": weights}
            )
            assert response.status_code == 200
            payload = response.json()
            assert payload["weights"] == {key: float(value) for key, value in weights.items()}
            assert payload["delivery_version"] == HEATMAP_DELIVERY_VERSION
            assert payload["cell_count"] == 36292
            assert "{z}/{x}/{y}.mvt" in payload["tile_url_template"]

        rejected = client.post(
            "/api/analysis/heatmap/prepare", json={"weights": {"unknown.metric": 100}}
        )
        assert rejected.status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_tile_contract_headers_empty_tile_and_validation(client: TestClient) -> None:
    app.dependency_overrides[get_heatmap_service] = lambda: FakeHeatmapService()
    signature = "a" * 64
    try:
        response = client.get(
            f"/api/analysis/heatmap/tiles/{signature}/11/1196/594.mvt?spec=opaque"
        )
        assert response.status_code == 200
        assert response.content == b"mvt"
        assert response.headers["content-type"].startswith(
            "application/vnd.mapbox-vector-tile"
        )
        assert response.headers["cache-control"] == "public, max-age=86400, immutable"
        assert response.headers["etag"] == f'"{"b" * 64}"'
        assert response.headers["x-kartaspb-scoring-signature"] == signature
        assert response.headers["x-kartaspb-heatmap-version"] == HEATMAP_DELIVERY_VERSION

        empty = client.get(
            f"/api/analysis/heatmap/tiles/{signature}/0/0/0.mvt?spec=opaque"
        )
        assert empty.status_code == 200
        assert empty.content == b""
        assert empty.headers["content-type"].startswith(
            "application/vnd.mapbox-vector-tile"
        )

        tampered = client.get(
            f"/api/analysis/heatmap/tiles/{signature}/11/1196/594.mvt?spec=tampered"
        )
        assert tampered.status_code == 422
        invalid_coordinate = client.get(
            f"/api/analysis/heatmap/tiles/{signature}/2/4/0.mvt?spec=opaque"
        )
        assert invalid_coordinate.status_code == 422
    finally:
        app.dependency_overrides.clear()
