from uuid import UUID

from fastapi.testclient import TestClient

from app.api.routes.analysis import get_analysis_grid_service
from app.data.analysis_grid import AnalysisGridMetadata
from app.main import app

DISTRICT_ID = UUID("00000000-0000-0000-0000-000000000001")


class FakeAnalysisGridService:
    def __init__(self) -> None:
        self.tile_calls: list[tuple[int, int, int]] = []

    def metadata(self) -> AnalysisGridMetadata:
        return AnalysisGridMetadata(
            grid_version="spb-square-200m-v1",
            cell_size_m=200,
            metric_srid=32636,
            display_srid=4326,
            cell_count=42,
            district_count=1,
            district_cell_counts=[{"district_id": DISTRICT_ID, "cell_count": 42}],
            bbox=[29.0, 59.0, 31.0, 61.0],
        )

    def tile(self, z: int, x: int, y: int) -> bytes:
        self.tile_calls.append((z, x, y))
        return b"\x1a\x00"


def test_analysis_grid_metadata_contract(client: TestClient) -> None:
    service = FakeAnalysisGridService()
    app.dependency_overrides[get_analysis_grid_service] = lambda: service
    try:
        response = client.get("/api/analysis/grid/meta")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "grid_version": "spb-square-200m-v1",
        "cell_size_m": 200,
        "metric_srid": 32636,
        "display_srid": 4326,
        "cell_count": 42,
        "district_count": 1,
        "district_cell_counts": [
            {"district_id": str(DISTRICT_ID), "cell_count": 42}
        ],
        "bbox": [29.0, 59.0, 31.0, 61.0],
    }


def test_analysis_grid_tile_contract(client: TestClient) -> None:
    service = FakeAnalysisGridService()
    app.dependency_overrides[get_analysis_grid_service] = lambda: service
    try:
        response = client.get("/api/analysis/grid/tiles/11/1196/594.mvt")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.content == b"\x1a\x00"
    assert response.headers["content-type"] == "application/vnd.mapbox-vector-tile"
    assert response.headers["cache-control"] == "public, max-age=86400"
    assert service.tile_calls == [(11, 1196, 594)]


def test_analysis_grid_rejects_out_of_extent_tile(client: TestClient) -> None:
    service = FakeAnalysisGridService()
    app.dependency_overrides[get_analysis_grid_service] = lambda: service
    try:
        response = client.get("/api/analysis/grid/tiles/2/4/0.mvt")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    assert service.tile_calls == []
