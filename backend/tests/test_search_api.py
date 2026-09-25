from uuid import UUID

from fastapi.testclient import TestClient

from app.api.routes.search import get_search_catalog_service
from app.data.districts import UnknownDistrictsError
from app.data.map_catalog import UnknownCategoriesError
from app.data.search_catalog import SearchResultData
from app.main import app


class FakeSearchService:
    def __init__(self) -> None:
        self.call: tuple[str, tuple[str, ...], tuple[UUID, ...], int] | None = None

    def search(
        self,
        query: str,
        categories: tuple[str, ...],
        district_ids: tuple[UUID, ...],
        limit: int,
    ) -> list[SearchResultData]:
        self.call = (query, categories, district_ids, limit)
        return [
            SearchResultData(
                id=UUID("c49e54e1-3481-4b07-9f81-0b161b57b62b"),
                name="Озерки",
                categories=["transport.stop"],
                object_kind="feature",
                geometry_type="Point",
                representative_point={"type": "Point", "coordinates": [30.3, 60.0]},
                bbox=(30.3, 60.0, 30.3, 60.0),
            )
        ]


def test_search_contract_and_defaults(client: TestClient) -> None:
    service = FakeSearchService()
    district = UUID("161ba369-c548-5569-9cc2-679522090220")
    app.dependency_overrides[get_search_catalog_service] = lambda: service
    try:
        response = client.get(
            "/api/search",
            params={
                "q": "  ЁЗЕРКИ ",
                "categories": "transport.stop,transport.stop",
                "districts": f"{district},{district}",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert service.call == ("езерки", ("transport.stop",), (district,), 20)
    assert response.json() == {
        "type": "SearchResults",
        "results": [
            {
                "id": "c49e54e1-3481-4b07-9f81-0b161b57b62b",
                "name": "Озерки",
                "categories": ["transport.stop"],
                "object_kind": "feature",
                "geometry_type": "Point",
                "representative_point": {
                    "type": "Point",
                    "coordinates": [30.3, 60.0],
                },
                "bbox": [30.3, 60.0, 30.3, 60.0],
            }
        ],
    }


def test_search_rejects_invalid_query_and_limit(client: TestClient) -> None:
    service = FakeSearchService()
    app.dependency_overrides[get_search_catalog_service] = lambda: service
    try:
        short = client.get("/api/search", params={"q": "x"})
        large_limit = client.get("/api/search", params={"q": "park", "limit": 51})
    finally:
        app.dependency_overrides.clear()

    assert short.status_code == 422
    assert short.json()["detail"]["code"] == "invalid_request"
    assert large_limit.status_code == 422


def test_search_errors_are_machine_readable(client: TestClient) -> None:
    class UnknownCategoryService(FakeSearchService):
        def search(
            self,
            query: str,
            categories: tuple[str, ...],
            district_ids: tuple[UUID, ...],
            limit: int,
        ) -> list[SearchResultData]:
            raise UnknownCategoriesError(["unknown"])

    app.dependency_overrides[get_search_catalog_service] = UnknownCategoryService
    try:
        unknown_category = client.get(
            "/api/search", params={"q": "park", "categories": "unknown"}
        )
    finally:
        app.dependency_overrides.clear()
    assert unknown_category.status_code == 422
    assert unknown_category.json()["detail"]["code"] == "unknown_category"

    class UnknownDistrictService(FakeSearchService):
        def search(
            self,
            query: str,
            categories: tuple[str, ...],
            district_ids: tuple[UUID, ...],
            limit: int,
        ) -> list[SearchResultData]:
            raise UnknownDistrictsError(list(district_ids), [])

    district = UUID("161ba369-c548-5569-9cc2-679522090220")
    app.dependency_overrides[get_search_catalog_service] = UnknownDistrictService
    try:
        unknown_district = client.get(
            "/api/search", params={"q": "park", "districts": str(district)}
        )
    finally:
        app.dependency_overrides.clear()
    assert unknown_district.status_code == 422
    assert unknown_district.json()["detail"]["code"] == "unknown_district"


def test_openapi_exposes_search_filters(client: TestClient) -> None:
    payload = client.get("/openapi.json").json()
    operation = payload["paths"]["/api/search"]["get"]

    assert {parameter["name"] for parameter in operation["parameters"]} == {
        "q",
        "categories",
        "districts",
        "limit",
    }
