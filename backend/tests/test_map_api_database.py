import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text


def database_url() -> str:
    value = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL")
    if value is None:
        pytest.skip("Set TEST_DATABASE_URL to run database integration tests")
    return value


@pytest.mark.integration
def test_real_postgis_map_and_detail_contracts(client: TestClient) -> None:
    engine = create_engine(database_url())
    token = uuid4().hex[:8]
    categories = [f"test.{token}.{kind}" for kind in ("point", "extra", "line", "polygon", "multi")]
    object_ids = [uuid4() for _ in range(4)]
    facility_id = uuid4()
    district_id = uuid4()
    district_object_id = uuid4()
    all_object_ids = [*object_ids, district_object_id]
    source_id: int | None = None
    try:
        with engine.begin() as connection:
            source_id = int(
                connection.scalar(
                    text("""
                        INSERT INTO meta.dataset_sources
                          (name,provider,source_type,source_url,version)
                        VALUES (:name,'fixture-provider','fixture','https://example.invalid','fixture-v1')
                        RETURNING id
                    """),
                    {"name": f"map-api-{token}"},
                )
            )
            run_id = int(
                connection.scalar(
                    text("""
                        INSERT INTO meta.import_runs
                          (source_id,status,source_version,started_at,finished_at)
                        VALUES (:source_id,'success','fixture-v1',now(),now()) RETURNING id
                    """),
                    {"source_id": source_id},
                )
            )
            connection.execute(
                text("""
                    INSERT INTO catalog.categories (key,label,enabled)
                    VALUES (:key,:label,true)
                """),
                [{"key": category, "label": category} for category in categories],
            )
            connection.execute(
                text("""
                    INSERT INTO catalog.objects
                      (id,object_kind,lifecycle_status,name,geom,properties,property_sources,revision)
                    VALUES
                      (:point,'feature','active','Fixture point',ST_Point(10,10,4326),'{}','{}',1),
                      (:line,'feature','active','Fixture line',
                       ST_GeomFromText(:line_wkt,4326),'{}','{}',1),
                      (:polygon,'feature','active','Fixture polygon',
                       ST_GeomFromText(:polygon_wkt,4326),'{}','{}',1),
                      (:multi,'feature','active','Fixture multipolygon',
                       ST_GeomFromText(:multi_wkt,4326),'{}','{}',1)
                      ,(:district,'boundary','active','Fixture district',
                       ST_GeomFromText(:district_wkt,4326),'{}','{}',1)
                """),
                {
                    "point": object_ids[0],
                    "line": object_ids[1],
                    "polygon": object_ids[2],
                    "multi": object_ids[3],
                    "district": district_object_id,
                    "line_wkt": "LINESTRING(10 10,10.1 10.1)",
                    "polygon_wkt": "POLYGON((10 10,10.1 10,10.1 10.1,10 10.1,10 10))",
                    "multi_wkt": (
                        "MULTIPOLYGON(((10.11 10.11,10.15 10.11,10.15 10.15,"
                        "10.11 10.15,10.11 10.11)))"
                    ),
                    "district_wkt": "POLYGON((9.8 9.8,10.3 9.8,10.3 10.3,9.8 10.3,9.8 9.8))",
                },
            )
            connection.execute(
                text("""
                    INSERT INTO domain.districts
                      (id,canonical_object_id,name,slug,display_order,enabled)
                    VALUES (:id,:object_id,'Fixture district',:slug,200,true)
                """),
                {"id": district_id, "object_id": district_object_id, "slug": f"map-{token}"},
            )
            connection.execute(
                text("""
                    INSERT INTO catalog.object_categories
                      (object_id,category_key,lifecycle_status)
                    VALUES
                      (:point,:point_category,'active'),
                      (:point,:extra_category,'active'),
                      (:line,:line_category,'active'),
                      (:polygon,:polygon_category,'active'),
                      (:multi,:multi_category,'active')
                """),
                {
                    "point": object_ids[0],
                    "line": object_ids[1],
                    "polygon": object_ids[2],
                    "multi": object_ids[3],
                    "point_category": categories[0],
                    "extra_category": categories[1],
                    "line_category": categories[2],
                    "polygon_category": categories[3],
                    "multi_category": categories[4],
                },
            )
            connection.execute(
                text("""
                    INSERT INTO catalog.object_sources
                      (object_id,source_id,source_object_type,source_object_id,
                       source_native_version,source_status,candidate_name,candidate_geom,
                       candidate_properties,payload_hash,geometry_quality,source_priority,
                       match_method,match_confidence,first_seen_import_run_id,
                       last_seen_import_run_id,last_changed_import_run_id)
                    SELECT object.id,:source_id,
                      CASE GeometryType(object.geom) WHEN 'POINT' THEN 'node' ELSE 'way' END,
                      row_number() OVER (ORDER BY object.id)::text,'fixture-v1','present',
                      object.name,object.geom,'{}'::jsonb,repeat('a',64),
                      CASE WHEN GeometryType(object.geom)='MULTIPOLYGON'
                           THEN 'assembled' ELSE 'raw' END,
                      0,'source_identity',1.000,:run_id,:run_id,:run_id
                    FROM catalog.objects object WHERE object.id=ANY(:object_ids)
                """),
                {"source_id": source_id, "run_id": run_id, "object_ids": object_ids},
            )

        response = client.get(
            "/api/map/features",
            params={
                "bbox": "9.9,9.9,10.2,10.2",
                "categories": ",".join(categories),
                "limit": 10,
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["type"] == "FeatureCollection"
        assert len(payload["features"]) == 4
        assert len({feature["id"] for feature in payload["features"]}) == 4
        assert {feature["geometry"]["type"] for feature in payload["features"]} == {
            "Point",
            "LineString",
            "Polygon",
            "MultiPolygon",
        }
        point = next(
            feature
            for feature in payload["features"]
            if feature["id"] == str(object_ids[0])
        )
        assert point["properties"]["canonical_id"] == str(object_ids[0])
        assert point["properties"]["facility_entity_id"] is None
        assert point["properties"]["member_canonical_ids"] == [str(object_ids[0])]
        assert point["properties"]["categories"] == sorted(categories[:2])

        with engine.begin() as connection:
            connection.execute(
                text("""
                    INSERT INTO domain.facility_entities
                      (id,category_key,representative_object_id,display_object_id,
                       analysis_object_id,lifecycle_status,link_method,evidence)
                    VALUES
                      (:id,:category,:point,:polygon,:polygon,'active','fixture','{}')
                """),
                {
                    "id": facility_id,
                    "category": categories[0],
                    "point": object_ids[0],
                    "polygon": object_ids[2],
                },
            )
            connection.execute(
                text("""
                    INSERT INTO domain.facility_entity_members
                      (facility_entity_id,canonical_object_id,geometry_role,
                       lifecycle_status,link_method,evidence)
                    VALUES
                      (:entity,:point,'POINT','active','fixture','{}'),
                      (:entity,:polygon,'FACILITY_SITE','active','fixture','{}')
                """),
                {"entity": facility_id, "point": object_ids[0], "polygon": object_ids[2]},
            )

        grouped = client.get(
            "/api/map/features",
            params={
                "bbox": "9.9,9.9,10.2,10.2",
                "categories": ",".join(categories),
                "districts": district_id,
                "limit": 10,
            },
        )
        assert grouped.status_code == 200, grouped.text
        grouped_features = grouped.json()["features"]
        assert len(grouped_features) == 3
        logical = next(feature for feature in grouped_features if feature["id"] == str(facility_id))
        assert logical["geometry"]["type"] == "Polygon"
        assert logical["properties"]["canonical_id"] == str(object_ids[0])
        assert logical["properties"]["display_canonical_id"] == str(object_ids[2])
        assert logical["properties"]["member_canonical_ids"] == sorted(
            [str(object_ids[0]), str(object_ids[2])]
        )
        assert sorted(logical["properties"]["categories"]) == sorted(
            [categories[0], categories[1], categories[3]]
        )

        grouped_by_point_category = client.get(
            "/api/map/features",
            params={"bbox": "9.9,9.9,10.2,10.2", "categories": categories[0], "limit": 10},
        )
        assert [feature["id"] for feature in grouped_by_point_category.json()["features"]] == [
            str(facility_id)
        ]

        limited = client.get(
            "/api/map/features",
            params={"bbox": "9.9,9.9,10.2,10.2", "categories": ",".join(categories), "limit": 2},
        )
        assert limited.status_code == 422
        assert limited.json()["detail"]["code"] == "feature_limit_exceeded"

        unknown = client.get(
            "/api/map/features",
            params={"bbox": "9.9,9.9,10.2,10.2", "categories": f"test.{token}.unknown"},
        )
        assert unknown.status_code == 422
        assert unknown.json()["detail"]["code"] == "unknown_category"

        empty = client.get(
            "/api/map/features",
            params={"bbox": "20,20,20.1,20.1", "categories": categories[0]},
        )
        assert empty.status_code == 200
        assert empty.json() == {"type": "FeatureCollection", "features": []}

        detail = client.get(f"/api/objects/{object_ids[0]}")
        assert detail.status_code == 200
        detail_payload = detail.json()
        assert detail_payload["name"] == "Fixture point"
        assert detail_payload["categories"] == sorted(categories[:2])
        assert detail_payload["geometry_type"] == "Point"
        assert detail_payload["facility"]["id"] == str(facility_id)
        assert detail_payload["facility"]["representative_object_id"] == str(object_ids[0])
        assert detail_payload["facility"]["display_object_id"] == str(object_ids[2])
        assert {member["canonical_id"] for member in detail_payload["facility"]["members"]} == {
            str(object_ids[0]),
            str(object_ids[2]),
        }
        assert detail_payload["sources"] == [
            {
                "provider": "fixture-provider",
                "object_type": "node",
                "object_id": detail_payload["sources"][0]["object_id"],
                "source_version": "fixture-v1",
                "geometry_quality": "raw",
            }
        ]
        serialized = str(detail_payload)
        for forbidden in (
            "payload_hash",
            "candidate_properties",
            "match_method",
            "import_run",
            "tags",
        ):
            assert forbidden not in serialized

        with engine.begin() as connection:
            connection.execute(
                text("UPDATE catalog.objects SET lifecycle_status='inactive' WHERE id=:id"),
                {"id": object_ids[0]},
            )
        assert client.get(f"/api/objects/{object_ids[0]}").status_code == 404
        assert client.get(f"/api/objects/{uuid4()}").status_code == 404
    finally:
        with engine.begin() as connection:
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
                text("DELETE FROM catalog.object_sources WHERE object_id=ANY(:ids)"),
                {"ids": object_ids},
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
                text("DELETE FROM catalog.categories WHERE key=ANY(:categories)"),
                {"categories": categories},
            )
            if source_id is not None:
                connection.execute(
                    text("DELETE FROM meta.dataset_sources WHERE id=:source_id"),
                    {"source_id": source_id},
                )
