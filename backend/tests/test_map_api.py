from typing import Any
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.api.routes.map import get_map_catalog_service
from app.data.districts import UnknownDistrictsError
from app.data.map_catalog import (
    FeatureLimitExceededError,
    MapFeatureData,
    ObjectDetailData,
    SourceSummaryData,
    UnknownCategoriesError,
)
from app.main import app


class FakeMapService:
    def __init__(self) -> None:
        self.limit: int | None = None
        self.categories: tuple[str, ...] | None = None
        self.district_ids: tuple[UUID, ...] | None = None
        self.feature = MapFeatureData(
            id=UUID("c49e54e1-3481-4b07-9f81-0b161b57b62b"),
            name="Озерки",
            object_kind="feature",
            geometry={"type": "Point", "coordinates": [30.3, 60.0]},
            categories=["healthcare.pharmacy", "transport.stop"],
        )

    def features(
        self,
        bbox: Any,
        categories: tuple[str, ...],
        limit: int,
        district_ids: tuple[UUID, ...] = (),
    ) -> list[MapFeatureData]:
        self.limit = limit
        self.categories = categories
        self.district_ids = district_ids
        return [self.feature]

    def object_detail(self, object_id: UUID) -> ObjectDetailData | None:
        if object_id != self.feature.id:
            return None
        return ObjectDetailData(
            id=self.feature.id,
            name=self.feature.name,
            categories=self.feature.categories,
            object_kind=self.feature.object_kind,
            geometry_type="Point",
            properties={},
            sources=[
                SourceSummaryData(
                    provider="OpenStreetMap",
                    object_type="node",
                    object_id="339394777",
                    source_version="fixture-v1",
                    geometry_quality="raw",
                )
            ],
        )


def test_map_features_contract_default_limit_and_multiple_categories(client: TestClient) -> None:
    service = FakeMapService()
    app.dependency_overrides[get_map_catalog_service] = lambda: service
    try:
        response = client.get(
            "/api/map/features",
            params={
                "bbox": "30.30,59.93,30.32,59.945",
                "categories": "healthcare.pharmacy,transport.stop",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert service.limit == 1000
    assert service.categories == ("healthcare.pharmacy", "transport.stop")
    assert service.district_ids == ()
    assert response.json() == {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "id": "c49e54e1-3481-4b07-9f81-0b161b57b62b",
                "geometry": {"type": "Point", "coordinates": [30.3, 60.0]},
                "properties": {
                    "canonical_id": "c49e54e1-3481-4b07-9f81-0b161b57b62b",
                    "name": "Озерки",
                    "categories": ["healthcare.pharmacy", "transport.stop"],
                    "object_kind": "feature",
                },
            }
        ],
    }


def test_map_features_accepts_max_limit_and_rejects_invalid_limit(client: TestClient) -> None:
    service = FakeMapService()
    app.dependency_overrides[get_map_catalog_service] = lambda: service
    try:
        accepted = client.get(
            "/api/map/features",
            params={"bbox": "30,59,30.1,59.1", "categories": "nature.park", "limit": 5000},
        )
        too_large = client.get(
            "/api/map/features",
            params={"bbox": "30,59,30.1,59.1", "categories": "nature.park", "limit": 5001},
        )
        zero = client.get(
            "/api/map/features",
            params={"bbox": "30,59,30.1,59.1", "categories": "nature.park", "limit": 0},
        )
    finally:
        app.dependency_overrides.clear()

    assert accepted.status_code == 200
    assert service.limit == 5000
    assert too_large.status_code == 422
    assert zero.status_code == 422


def test_map_features_parses_districts_and_normalizes_duplicates(client: TestClient) -> None:
    service = FakeMapService()
    app.dependency_overrides[get_map_catalog_service] = lambda: service
    district_id = UUID("161ba369-c548-5569-9cc2-679522090220")
    try:
        response = client.get(
            "/api/map/features",
            params={
                "bbox": "30,59,30.1,59.1",
                "categories": "nature.park",
                "districts": f"{district_id},{district_id}",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert service.district_ids == (district_id,)


def test_map_errors_are_machine_readable(client: TestClient) -> None:
    class UnknownService(FakeMapService):
        def features(
            self,
            bbox: Any,
            categories: tuple[str, ...],
            limit: int,
            district_ids: tuple[UUID, ...] = (),
        ) -> list[MapFeatureData]:
            del district_ids
            raise UnknownCategoriesError(["unknown"])

    app.dependency_overrides[get_map_catalog_service] = UnknownService
    try:
        unknown = client.get(
            "/api/map/features",
            params={"bbox": "30,59,30.1,59.1", "categories": "unknown"},
        )
    finally:
        app.dependency_overrides.clear()
    assert unknown.status_code == 422
    assert unknown.json()["detail"]["code"] == "unknown_category"

    class LimitedService(FakeMapService):
        def features(
            self,
            bbox: Any,
            categories: tuple[str, ...],
            limit: int,
            district_ids: tuple[UUID, ...] = (),
        ) -> list[MapFeatureData]:
            del district_ids
            raise FeatureLimitExceededError(limit)

    app.dependency_overrides[get_map_catalog_service] = LimitedService
    try:
        limited = client.get(
            "/api/map/features",
            params={"bbox": "30,59,30.1,59.1", "categories": "transport.road", "limit": 2},
        )
        invalid_bbox = client.get(
            "/api/map/features",
            params={"bbox": "31,59,30,60", "categories": "transport.road"},
        )
    finally:
        app.dependency_overrides.clear()
    assert limited.status_code == 422
    assert limited.json()["detail"] == {
        "code": "feature_limit_exceeded",
        "message": "The viewport contains more features than the requested limit",
        "requested_limit": 2,
        "suggestion": "zoom_in_or_disable_layers",
    }
    assert invalid_bbox.status_code == 422
    assert invalid_bbox.json()["detail"]["code"] == "invalid_request"

    district_id = UUID("161ba369-c548-5569-9cc2-679522090220")

    class UnknownDistrictService(FakeMapService):
        def features(
            self,
            bbox: Any,
            categories: tuple[str, ...],
            limit: int,
            district_ids: tuple[UUID, ...] = (),
        ) -> list[MapFeatureData]:
            del bbox, categories, limit, district_ids
            raise UnknownDistrictsError([district_id], [])

    app.dependency_overrides[get_map_catalog_service] = UnknownDistrictService
    try:
        unknown_district = client.get(
            "/api/map/features",
            params={
                "bbox": "30,59,30.1,59.1",
                "categories": "nature.park",
                "districts": str(district_id),
            },
        )
    finally:
        app.dependency_overrides.clear()
    assert unknown_district.status_code == 422
    assert unknown_district.json()["detail"] == {
        "code": "unknown_district",
        "message": "One or more districts are unknown or disabled",
        "unknown_districts": [str(district_id)],
    }


def test_object_detail_contract_not_found_and_invalid_uuid(client: TestClient) -> None:
    service = FakeMapService()
    app.dependency_overrides[get_map_catalog_service] = lambda: service
    try:
        found = client.get(f"/api/objects/{service.feature.id}")
        missing = client.get(f"/api/objects/{uuid4()}")
        invalid = client.get("/api/objects/not-a-uuid")
    finally:
        app.dependency_overrides.clear()

    assert found.status_code == 200
    assert found.json()["geometry_type"] == "Point"
    assert found.json()["sources"] == [
        {
            "provider": "OpenStreetMap",
            "object_type": "node",
            "object_id": "339394777",
            "source_version": "fixture-v1",
            "geometry_quality": "raw",
        }
    ]
    assert missing.status_code == 404
    assert invalid.status_code == 422


def test_openapi_and_docs_expose_map_endpoints(client: TestClient) -> None:
    schema = client.get("/openapi.json")

    assert schema.status_code == 200
    assert "/api/map/features" in schema.json()["paths"]
    assert "/api/objects/{object_id}" in schema.json()["paths"]
    assert client.get("/docs").status_code == 200


def test_cors_allows_only_configured_frontend_origins(client: TestClient) -> None:
    allowed = client.options(
        "/api/map/features",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    denied = client.options(
        "/api/map/features",
        headers={
            "Origin": "https://example.invalid",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert denied.status_code == 400
    assert "access-control-allow-origin" not in denied.headers
