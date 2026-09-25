import os
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text


def database_url() -> str:
    value = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL")
    if value is None:
        pytest.skip("Set TEST_DATABASE_URL to run database integration tests")
    return value


@pytest.mark.integration
def test_search_ranking_filters_geometry_and_duplicate_names(client: TestClient) -> None:
    engine = create_engine(database_url())
    token = uuid4().hex[:8]
    category_a = f"test.search.a.{token}"
    category_b = f"test.search.b.{token}"
    district_id = uuid4()
    district_object_id = UUID("10000000-0000-0000-0000-000000000100")
    object_ids = [
        UUID("10000000-0000-0000-0000-000000000101"),
        UUID("10000000-0000-0000-0000-000000000102"),
        UUID("10000000-0000-0000-0000-000000000103"),
        UUID("10000000-0000-0000-0000-000000000104"),
        UUID("10000000-0000-0000-0000-000000000105"),
        UUID("10000000-0000-0000-0000-000000000106"),
    ]
    all_object_ids = [district_object_id, *object_ids]
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO catalog.categories (key,label,enabled) "
                    "VALUES (:a,:a_label,true),(:b,:b_label,true)"
                ),
                {
                    "a": category_a,
                    "a_label": category_a,
                    "b": category_b,
                    "b_label": category_b,
                },
            )
            connection.execute(
                text(
                    """
                    INSERT INTO catalog.objects
                      (id,object_kind,lifecycle_status,name,geom,properties,
                       property_sources,revision)
                    VALUES
                      (:district,'boundary','active','Search fixture district',
                       ST_GeomFromText(
                         'POLYGON((10 10,10.5 10,10.5 10.5,10 10.5,10 10))',4326
                       ),'{}','{}',1),
                      (:exact1,'feature','active','Аптека',
                       ST_Point(10.1,10.1,4326),'{}','{}',1),
                      (:exact2,'feature','active','АПТЕКА',
                       ST_Point(10.2,10.2,4326),'{}','{}',1),
                      (:partial,'feature','active','Аптека Озерки',
                       ST_Point(11,11,4326),'{}','{}',1),
                      (:yo,'feature','active','Ёлочная аптека',
                       ST_Point(10.3,10.3,4326),'{}','{}',1),
                      (:park,'feature','active','Невский парк',
                       ST_GeomFromText(
                         'POLYGON((10.15 10.15,10.25 10.15,10.25 10.25,'
                         '10.15 10.25,10.15 10.15))',4326
                       ),'{}','{}',1),
                      (:inactive,'feature','inactive','Аптека закрыта',
                       ST_Point(10.4,10.4,4326),'{}','{}',1)
                    """
                ),
                {
                    "district": district_object_id,
                    "exact1": object_ids[0],
                    "exact2": object_ids[1],
                    "partial": object_ids[2],
                    "yo": object_ids[3],
                    "park": object_ids[4],
                    "inactive": object_ids[5],
                },
            )
            connection.execute(
                text(
                    """
                    INSERT INTO domain.districts
                      (id,canonical_object_id,name,slug,display_order,enabled)
                    VALUES (:id,:object_id,'Search fixture district',:slug,100,true)
                    """
                ),
                {
                    "id": district_id,
                    "object_id": district_object_id,
                    "slug": f"search-fixture-{token}",
                },
            )
            connection.execute(
                text(
                    """
                    INSERT INTO catalog.object_categories
                      (object_id,category_key,lifecycle_status)
                    VALUES
                      (:exact1,:a,'active'),
                      (:exact2,:a,'active'),
                      (:partial,:a,'active'),
                      (:yo,:a,'active'),
                      (:exact2,:b,'active'),
                      (:park,:b,'active')
                    """
                ),
                {
                    "exact1": object_ids[0],
                    "exact2": object_ids[1],
                    "partial": object_ids[2],
                    "yo": object_ids[3],
                    "park": object_ids[4],
                    "a": category_a,
                    "b": category_b,
                },
            )

        ranked = client.get(
            "/api/search",
            params={"q": "аптека", "categories": category_a, "limit": 10},
        )
        assert ranked.status_code == 200, ranked.text
        ranked_results = ranked.json()["results"]
        assert [item["id"] for item in ranked_results] == [
            str(object_ids[0]),
            str(object_ids[2]),
            str(object_ids[3]),
            str(object_ids[1]),
        ]
        assert len({item["id"] for item in ranked_results}) == 4
        assert all("score" not in item for item in ranked_results)

        normalized_yo = client.get(
            "/api/search", params={"q": "елочная", "categories": category_a}
        )
        assert normalized_yo.status_code == 200
        assert [item["id"] for item in normalized_yo.json()["results"]] == [
            str(object_ids[3])
        ]

        category_filtered = client.get(
            "/api/search", params={"q": "аптека", "categories": category_b}
        )
        assert category_filtered.status_code == 200
        assert [item["id"] for item in category_filtered.json()["results"]] == [
            str(object_ids[1])
        ]

        district_filtered = client.get(
            "/api/search",
            params={
                "q": "аптека",
                "categories": category_a,
                "districts": district_id,
            },
        )
        assert district_filtered.status_code == 200
        assert {item["id"] for item in district_filtered.json()["results"]} == {
            str(object_ids[0]),
            str(object_ids[1]),
            str(object_ids[3]),
        }

        polygon = client.get(
            "/api/search", params={"q": "невский парк", "categories": category_b}
        )
        assert polygon.status_code == 200
        polygon_result = polygon.json()["results"][0]
        assert polygon_result["geometry_type"] == "Polygon"
        assert polygon_result["representative_point"]["type"] == "Point"
        assert polygon_result["bbox"] == [10.15, 10.15, 10.25, 10.25]
        assert polygon_result["categories"] == [category_b]

        unknown_category = client.get(
            "/api/search",
            params={"q": "аптека", "categories": f"test.missing.{token}"},
        )
        assert unknown_category.status_code == 422
        assert unknown_category.json()["detail"]["code"] == "unknown_category"

        unknown_district = client.get(
            "/api/search", params={"q": "аптека", "districts": uuid4()}
        )
        assert unknown_district.status_code == 422
        assert unknown_district.json()["detail"]["code"] == "unknown_district"
    finally:
        with engine.begin() as connection:
            connection.execute(
                text("DELETE FROM domain.districts WHERE id=:id"), {"id": district_id}
            )
            connection.execute(
                text("DELETE FROM catalog.object_categories WHERE object_id=ANY(:ids)"),
                {"ids": all_object_ids},
            )
            connection.execute(
                text("DELETE FROM catalog.objects WHERE id=ANY(:ids)"),
                {"ids": all_object_ids},
            )
            connection.execute(
                text("DELETE FROM catalog.categories WHERE key=ANY(:keys)"),
                {"keys": [category_a, category_b]},
            )
