from fastapi.testclient import TestClient

from app.analytics.influence import (
    INFLUENCE_DELIVERY_VERSION,
    InfluenceChannel,
    InfluenceError,
    InfluenceTile,
    PreparedInfluence,
)
from app.api.routes.analysis import get_influence_service
from app.main import app


class FakeInfluenceService:
    def prepare(self, grid_version: str, metric_keys: list[str]) -> PreparedInfluence:
        if "unknown" in metric_keys:
            raise InfluenceError("unknown or unsupported influence metric")
        channels = tuple(
            InfluenceChannel(key, f"00000000-0000-0000-0000-{index + 1:012d}", f"score_{index}")
            for index, key in enumerate(sorted(metric_keys))
        )
        return PreparedInfluence(
            grid_version=grid_version,
            influence_signature="a" * 64,
            spec="immutable-spec",
            cell_count=36292,
            channels=channels,
            tile_url_template=(
                f"/api/analysis/influence/tiles/{'a' * 64}/"
                "{z}/{x}/{y}.mvt?spec=immutable-spec"
            ),
        )

    def tile(
        self,
        requested_signature: str,
        z: int,
        x: int,
        y: int,
        encoded_spec: str,
    ) -> InfluenceTile:
        if encoded_spec == "tampered":
            raise InfluenceError("influence signature does not match spec")
        return InfluenceTile(
            payload=b"" if (x, y) == (0, 0) else b"mvt",
            etag="b" * 64,
            influence_signature=requested_signature,
        )


def test_influence_prepare_is_bounded_and_returns_stable_channels(client: TestClient) -> None:
    app.dependency_overrides[get_influence_service] = lambda: FakeInfluenceService()
    try:
        response = client.post(
            "/api/analysis/influence/prepare",
            json={
                "metric_keys": [
                    "nature.park.accessibility_index",
                    "education.school.accessibility_index",
                ]
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert [item["metric_key"] for item in payload["channels"]] == [
            "education.school.accessibility_index",
            "nature.park.accessibility_index",
        ]
        assert [item["property_name"] for item in payload["channels"]] == ["score_0", "score_1"]
        assert payload["delivery_version"] == INFLUENCE_DELIVERY_VERSION
        assert payload["cell_count"] == 36292

        rejected = client.post(
            "/api/analysis/influence/prepare", json={"metric_keys": ["unknown"]}
        )
        assert rejected.status_code == 422
        too_many = client.post(
            "/api/analysis/influence/prepare",
            json={"metric_keys": [f"metric.{index}" for index in range(9)]},
        )
        assert too_many.status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_influence_tile_contract_and_immutable_cache_headers(client: TestClient) -> None:
    app.dependency_overrides[get_influence_service] = lambda: FakeInfluenceService()
    signature = "a" * 64
    try:
        response = client.get(
            f"/api/analysis/influence/tiles/{signature}/11/1196/594.mvt?spec=immutable"
        )
        assert response.status_code == 200
        assert response.content == b"mvt"
        assert response.headers["cache-control"] == "public, max-age=86400, immutable"
        assert response.headers["x-kartaspb-influence-signature"] == signature
        assert response.headers["x-kartaspb-influence-version"] == INFLUENCE_DELIVERY_VERSION
        assert response.headers["etag"] == f'"{"b" * 64}"'

        invalid = client.get(
            f"/api/analysis/influence/tiles/{signature}/11/1196/594.mvt?spec=tampered"
        )
        assert invalid.status_code == 422
        out_of_bounds = client.get(
            f"/api/analysis/influence/tiles/{signature}/2/4/0.mvt?spec=immutable"
        )
        assert out_of_bounds.status_code == 422
    finally:
        app.dependency_overrides.clear()
