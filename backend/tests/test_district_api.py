from uuid import UUID

from fastapi.testclient import TestClient

from app.api.routes.districts import get_district_catalog_service
from app.data.districts import DistrictData, DistrictGeometryData, UnknownDistrictsError
from app.main import app


class FakeDistrictService:
    def __init__(self) -> None:
        self.geometry_calls: list[tuple[UUID, ...]] = []

    def districts(self) -> list[DistrictData]:
        return [
            DistrictData(
                id=UUID("161ba369-c548-5569-9cc2-679522090220"),
                name="Центральный",
                slug="centralny",
                bbox=(30.30827, 59.91385, 30.40312, 59.95792),
                display_order=18,
            )
        ]

    def geometries(self, district_ids: tuple[UUID, ...]) -> list[DistrictGeometryData]:
        self.geometry_calls.append(district_ids)
        records = {
            UUID("161ba369-c548-5569-9cc2-679522090220"): DistrictGeometryData(
                id=UUID("161ba369-c548-5569-9cc2-679522090220"),
                name="Центральный",
                slug="centralny",
                geometry={
                    "type": "Polygon",
                    "coordinates": [[[30.3, 59.9], [30.4, 59.9], [30.3, 59.9]]],
                },
            ),
            UUID("b0d2b52a-0f4a-519a-ae6c-138d4d4b2af1"): DistrictGeometryData(
                id=UUID("b0d2b52a-0f4a-519a-ae6c-138d4d4b2af1"),
                name="Кронштадтский",
                slug="kronshtadtsky",
                geometry={
                    "type": "MultiPolygon",
                    "coordinates": [[[[29.7, 59.9], [29.8, 59.9], [29.7, 59.9]]]],
                },
            ),
        }
        return [records[item] for item in district_ids]


def test_district_list_contract_is_lightweight(client: TestClient) -> None:
    app.dependency_overrides[get_district_catalog_service] = FakeDistrictService
    try:
        response = client.get("/api/districts")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "districts": [
            {
                "id": "161ba369-c548-5569-9cc2-679522090220",
                "name": "Центральный",
                "slug": "centralny",
                "bbox": [30.30827, 59.91385, 30.40312, 59.95792],
                "display_order": 18,
            }
        ]
    }
    assert "geometry" not in response.text


def test_openapi_exposes_district_list_and_map_parameter(client: TestClient) -> None:
    schema = client.get("/openapi.json")

    assert schema.status_code == 200
    payload = schema.json()
    assert "/api/districts" in payload["paths"]
    assert "/api/districts/geometry" in payload["paths"]
    parameters = payload["paths"]["/api/map/features"]["get"]["parameters"]
    assert "districts" in {parameter["name"] for parameter in parameters}


def test_district_geometry_returns_one_batch_feature_collection(client: TestClient) -> None:
    central = UUID("161ba369-c548-5569-9cc2-679522090220")
    kronstadt = UUID("b0d2b52a-0f4a-519a-ae6c-138d4d4b2af1")
    service = FakeDistrictService()
    app.dependency_overrides[get_district_catalog_service] = lambda: service
    try:
        response = client.get(
            "/api/districts/geometry",
            params={"districts": f"{central},{kronstadt},{central}"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert service.geometry_calls == [(central, kronstadt)]
    payload = response.json()
    assert payload["type"] == "FeatureCollection"
    assert [feature["id"] for feature in payload["features"]] == [str(central), str(kronstadt)]
    assert [feature["geometry"]["type"] for feature in payload["features"]] == [
        "Polygon",
        "MultiPolygon",
    ]
    assert payload["features"][0]["properties"] == {
        "id": str(central),
        "name": "Центральный",
        "slug": "centralny",
    }
    assert set(payload["features"][0]) == {"type", "id", "properties", "geometry"}
    assert "canonical" not in response.text
    assert "osm" not in response.text


def test_district_geometry_reuses_request_and_registry_validation(client: TestClient) -> None:
    unknown = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")

    class UnknownDistrictService(FakeDistrictService):
        def geometries(self, district_ids: tuple[UUID, ...]) -> list[DistrictGeometryData]:
            raise UnknownDistrictsError(list(district_ids), [])

    app.dependency_overrides[get_district_catalog_service] = UnknownDistrictService
    try:
        invalid = client.get(
            "/api/districts/geometry", params={"districts": "not-a-uuid"}
        )
        missing = client.get(
            "/api/districts/geometry", params={"districts": str(unknown)}
        )
    finally:
        app.dependency_overrides.clear()

    assert invalid.status_code == 422
    assert invalid.json()["detail"]["code"] == "invalid_request"
    assert missing.status_code == 422
    assert missing.json()["detail"] == {
        "code": "unknown_district",
        "message": "One or more districts are unknown or disabled",
        "unknown_districts": [str(unknown)],
    }
