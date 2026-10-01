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
        UUID("10000000-0000-0000-0000-000000000107"),
        UUID("10000000-0000-0000-0000-000000000108"),
    ]
    all_object_ids = [district_object_id, *object_ids]
    facility_id = uuid4()
    street_id = uuid4()
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
                      (:partial,'feature','active','Аптека Озерки',
                       ST_Point(11,11,4326),'{}','{}',1),
                      (:yo,'feature','active','Ёлочная аптека',
                       ST_Point(10.3,10.3,4326),'{}','{}',1),
                      (:park,'feature','active','Невский парк',
                       ST_GeomFromText(
                         'POLYGON((10.15 10.15,10.25 10.15,10.25 10.25,'
                         '10.15 10.25,10.15 10.15))',4326
                       ),'{}','{}',1),
                      (:inactive,'feature','inactive','Аптека закрыта',
                       ST_Point(10.4,10.4,4326),'{}','{}',1),
                      (:line,'feature','active','Search midpoint road',
                       ST_GeomFromText(
                         'LINESTRING(10.1 10.1,10.3 10.1)',4326
                       ),'{}','{}',1),
                      (:multipolygon,'feature','active','Search multipolygon area',
                       ST_GeomFromText(
                         'MULTIPOLYGON(((12 12,12.2 12,12.2 12.2,12 12.2,12 12)),'
                         '((13 13,13.4 13,13.4 13.4,13 13.4,13 13)))',4326
                       ),'{}','{}',1)
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
                    "line": object_ids[6],
                    "multipolygon": object_ids[7],
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
                      (:park,:b,'active'),
                      (:line,:b,'active'),
                      (:multipolygon,:b,'active')
                    """
                ),
                {
                    "exact1": object_ids[0],
                    "exact2": object_ids[1],
                    "partial": object_ids[2],
                    "yo": object_ids[3],
                    "park": object_ids[4],
                    "line": object_ids[6],
                    "multipolygon": object_ids[7],
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
        assert all(item["result_type"] == "object" for item in ranked_results)
        assert all(item["detail_object_id"] == item["id"] for item in ranked_results)
        assert all("score" not in item for item in ranked_results)
        assert ranked_results[0]["representative_point"] == {
            "type": "Point",
            "coordinates": [10.1, 10.1],
        }

        with engine.begin() as connection:
            connection.execute(
                text("""
                    INSERT INTO domain.facility_entities
                      (id,category_key,representative_object_id,display_object_id,
                       analysis_object_id,lifecycle_status,link_method,evidence)
                    VALUES (:id,:category,:point,:area,:point,'active','fixture','{}')
                """),
                {
                    "id": facility_id,
                    "category": category_a,
                    "point": object_ids[0],
                    "area": object_ids[4],
                },
            )
            connection.execute(
                text("""
                    INSERT INTO domain.facility_entity_members
                      (facility_entity_id,canonical_object_id,geometry_role,
                       lifecycle_status,link_method,evidence)
                    VALUES
                      (:entity,:point,'POINT','active','fixture','{}'),
                      (:entity,:area,'FACILITY_SITE','active','fixture','{}')
                """),
                {"entity": facility_id, "point": object_ids[0], "area": object_ids[4]},
            )

        representation_search = client.get(
            "/api/search", params={"q": "аптека", "categories": category_a, "limit": 10}
        )
        assert representation_search.status_code == 200
        represented = next(
            item
            for item in representation_search.json()["results"]
            if item["id"] == str(facility_id)
        )
        assert represented["result_type"] == "facility"
        assert represented["detail_object_id"] == str(object_ids[0])
        assert represented["geometry_type"] == "Polygon"
        assert represented["bbox"] == [10.15, 10.15, 10.25, 10.25]
        assert represented["representative_point"] == {
            "type": "Point",
            "coordinates": [10.2, 10.2],
        }
        represented_ids = {item["id"] for item in representation_search.json()["results"]}
        assert str(object_ids[0]) not in represented_ids
        assert str(object_ids[4]) not in represented_ids
        collapsed_limit = client.get(
            "/api/search", params={"q": "аптека", "categories": category_a, "limit": 1}
        )
        assert [item["id"] for item in collapsed_limit.json()["results"]] == [
            str(facility_id)
        ]

        normalized_nbsp = client.get(
            "/api/search", params={"q": "аптека озерки", "categories": category_a}
        )
        assert normalized_nbsp.status_code == 200
        assert [item["id"] for item in normalized_nbsp.json()["results"]] == [
            str(object_ids[2])
        ]

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
            str(facility_id),
            str(object_ids[1]),
            str(object_ids[3]),
        }

        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO domain.street_entities
                      (id,display_name,search_name,geom,representative_point,
                       lifecycle_status,link_method,evidence)
                    VALUES (:id,'Search midpoint road','search midpoint road',
                      ST_GeomFromText('MULTILINESTRING((10.1 10.1,10.3 10.1))',4326),
                      ST_Point(10.2,10.1,4326),'active','fixture','{}')
                    """
                ),
                {"id": street_id},
            )
            connection.execute(
                text(
                    """
                    INSERT INTO domain.street_entity_members
                      (street_entity_id,canonical_object_id,lifecycle_status,
                       link_method,evidence)
                    VALUES (:street,:object,'active','fixture','{}')
                    """
                ),
                {"street": street_id, "object": object_ids[6]},
            )

        line = client.get("/api/search", params={"q": "search midpoint road"})
        assert line.status_code == 200
        line_result = line.json()["results"][0]
        assert line_result["id"] == str(street_id)
        assert line_result["result_type"] == "street"
        assert line_result["detail_object_id"] is None
        assert line_result["geometry_type"] == "MultiLineString"
        assert line_result["representative_point"] == {
            "type": "Point",
            "coordinates": [10.2, 10.1],
        }
        street_only = client.get(
            "/api/search",
            params={"q": "search midpoint road", "include_objects": "false"},
        )
        assert [item["id"] for item in street_only.json()["results"]] == [str(street_id)]

        district_street = client.get(
            "/api/search",
            params={"q": "search midpoint road", "districts": district_id},
        )
        assert [item["id"] for item in district_street.json()["results"]] == [
            str(street_id)
        ]

        multipolygon = client.get(
            "/api/search",
            params={"q": "search multipolygon area", "categories": category_b},
        )
        assert multipolygon.status_code == 200
        multipolygon_result = multipolygon.json()["results"][0]
        assert multipolygon_result["geometry_type"] == "MultiPolygon"
        assert multipolygon_result["representative_point"] == {
            "type": "Point",
            "coordinates": [13.2, 13.2],
        }

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
                text("DELETE FROM domain.street_entity_members WHERE street_entity_id=:id"),
                {"id": street_id},
            )
            connection.execute(
                text("DELETE FROM domain.street_entities WHERE id=:id"),
                {"id": street_id},
            )
            connection.execute(
                text("DELETE FROM domain.facility_entity_members WHERE facility_entity_id=:id"),
                {"id": facility_id},
            )
            connection.execute(
                text("DELETE FROM domain.facility_entities WHERE id=:id"),
                {"id": facility_id},
            )
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
