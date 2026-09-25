from uuid import UUID

from fastapi.testclient import TestClient

from app.api.routes.districts import get_district_catalog_service
from app.data.districts import DistrictData
from app.main import app


class FakeDistrictService:
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
    parameters = payload["paths"]["/api/map/features"]["get"]["parameters"]
    assert "districts" in {parameter["name"] for parameter in parameters}
