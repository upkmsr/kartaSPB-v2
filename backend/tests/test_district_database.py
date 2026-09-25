import json
import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.data.districts import DISTRICT_DEFINITIONS, bootstrap_districts


def database_url() -> str:
    value = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL")
    if value is None:
        pytest.skip("Set TEST_DATABASE_URL to run database integration tests")
    return value


@pytest.mark.integration
def test_district_registry_and_spatial_map_contracts(client: TestClient) -> None:
    engine = create_engine(database_url())
    token = uuid4().hex[:8]
    source_id: int | None = None
    feature_ids = [uuid4() for _ in range(5)]
    category = f"test.district.{token}"
    saved_registry: list[dict[str, object]] = []
    canonical_ids = {item.relation_id: uuid4() for item in DISTRICT_DEFINITIONS}
    try:
        with engine.begin() as connection:
            saved_registry = [dict(row._mapping) for row in connection.execute(
                text("SELECT * FROM domain.districts ORDER BY display_order")
            )]
            connection.execute(text("DELETE FROM domain.districts"))
            source_id = int(
                connection.scalar(
                    text(
                        """
                        INSERT INTO meta.dataset_sources
                          (name,provider,source_type,source_url,version)
                        VALUES (:name,'OpenStreetMap','osm_pbf',
                                'https://example.invalid/districts','fixture-v1')
                        RETURNING id
                        """
                    ),
                    {"name": f"district-api-{token}"},
                )
            )
            run_id = int(
                connection.scalar(
                    text(
                        """
                        INSERT INTO meta.import_runs
                          (source_id,status,source_version,started_at,finished_at)
                        VALUES (:source_id,'success','fixture-v1',now(),now())
                        RETURNING id
                        """
                    ),
                    {"source_id": source_id},
                )
            )
            relation_rows = [
                {
                    "osm_id": 337422,
                    "tags": json.dumps(
                        {
                            "type": "boundary",
                            "boundary": "administrative",
                            "admin_level": "4",
                            "wikidata": "Q656",
                        }
                    ),
                },
                *[
                    {
                        "osm_id": item.relation_id,
                        "tags": json.dumps(
                            {
                                "type": "boundary",
                                "boundary": "administrative",
                                "admin_level": "5",
                                "name": item.name,
                            }
                        ),
                    }
                    for item in DISTRICT_DEFINITIONS
                ],
            ]
            connection.execute(
                text(
                    """
                    INSERT INTO staging.osm_relations
                      (source_id,osm_id,tags,import_run_id)
                    VALUES (:source_id,:osm_id,CAST(:tags AS jsonb),:run_id)
                    """
                ),
                [dict(row, source_id=source_id, run_id=run_id) for row in relation_rows],
            )
            connection.execute(
                text(
                    """
                    INSERT INTO staging.osm_relation_members
                      (source_id,relation_id,sequence,member_type,member_id,role,import_run_id)
                    VALUES (:source_id,337422,:sequence,'relation',:member_id,'subarea',:run_id)
                    """
                ),
                [
                    {
                        "source_id": source_id,
                        "sequence": index,
                        "member_id": item.relation_id,
                        "run_id": run_id,
                    }
                    for index, item in enumerate(DISTRICT_DEFINITIONS)
                ],
            )
            for index, item in enumerate(DISTRICT_DEFINITIONS):
                min_lon = 10 + index * 0.05
                geometry = (
                    f"POLYGON(({min_lon} 10,{min_lon + 0.05} 10,"
                    f"{min_lon + 0.05} 10.05,{min_lon} 10.05,{min_lon} 10))"
                )
                connection.execute(
                    text(
                        """
                        INSERT INTO catalog.objects
                          (id,object_kind,lifecycle_status,name,geom,properties,
                           property_sources,revision)
                        VALUES (:id,'boundary','active',:name,
                                ST_GeomFromText(:geometry,4326),'{}','{}',1)
                        """
                    ),
                    {
                        "id": canonical_ids[item.relation_id],
                        "name": item.name,
                        "geometry": geometry,
                    },
                )
                connection.execute(
                    text(
                        """
                        INSERT INTO catalog.object_sources
                          (object_id,source_id,source_object_type,source_object_id,
                           source_native_version,source_status,candidate_name,candidate_geom,
                           candidate_properties,payload_hash,geometry_quality,source_priority,
                           match_method,match_confidence,first_seen_import_run_id,
                           last_seen_import_run_id,last_changed_import_run_id)
                        SELECT :object_id,:source_id,'relation',:relation_id,'fixture-v1',
                               'present',:name,geom,'{}',repeat('d',64),'assembled',0,
                               'source_identity',1.000,:run_id,:run_id,:run_id
                        FROM catalog.objects WHERE id=:object_id
                        """
                    ),
                    {
                        "object_id": canonical_ids[item.relation_id],
                        "source_id": source_id,
                        "relation_id": str(item.relation_id),
                        "name": item.name,
                        "run_id": run_id,
                    },
                )
            connection.execute(
                text(
                    "INSERT INTO catalog.categories (key,label,enabled) "
                    "VALUES (:key,:label,true)"
                ),
                {"key": category, "label": category},
            )
            connection.execute(
                text(
                    """
                    INSERT INTO catalog.objects
                      (id,object_kind,lifecycle_status,name,geom,properties,property_sources,revision)
                    VALUES
                      (:inside,'feature','active','Inside district 1',
                       ST_Point(10.02,10.02,4326),'{}','{}',1),
                      (:outside,'feature','active','Inside district 2',
                       ST_Point(10.08,10.02,4326),'{}','{}',1),
                      (:crossing,'feature','active','Crosses districts',
                       ST_GeomFromText('LINESTRING(10.04 10.02,10.06 10.02)',4326),'{}','{}',1),
                      (:polygon,'feature','active','Polygon in district 1',
                       ST_GeomFromText(
                         'POLYGON((10.01 10.01,10.03 10.01,10.03 10.03,10.01 10.03,10.01 10.01))',
                         4326),'{}','{}',1),
                      (:multi,'feature','active','MultiPolygon in district 2',
                       ST_GeomFromText(
                         'MULTIPOLYGON(((10.07 10.01,10.09 10.01,10.09 10.03,'
                         '10.07 10.03,10.07 10.01)))',
                         4326),'{}','{}',1)
                    """
                ),
                {
                    "inside": feature_ids[0],
                    "outside": feature_ids[1],
                    "crossing": feature_ids[2],
                    "polygon": feature_ids[3],
                    "multi": feature_ids[4],
                },
            )
            connection.execute(
                text(
                    """
                    INSERT INTO catalog.object_categories
                      (object_id,category_key,lifecycle_status)
                    SELECT unnest(CAST(:ids AS uuid[])),:category,'active'
                    """
                ),
                {"ids": feature_ids, "category": category},
            )

        first = bootstrap_districts(engine=engine, source_id=source_id)
        with engine.connect() as connection:
            initial = connection.execute(
                text(
                    """
                    SELECT id,canonical_object_id,slug,display_order,enabled,
                           created_at,updated_at
                    FROM domain.districts ORDER BY display_order
                    """
                )
            ).all()
        second = bootstrap_districts(engine=engine, source_id=source_id)
        with engine.connect() as connection:
            repeated = connection.execute(
                text(
                    """
                    SELECT id,canonical_object_id,slug,display_order,enabled,
                           created_at,updated_at
                    FROM domain.districts ORDER BY display_order
                    """
                )
            ).all()
            quality = connection.execute(
                text(
                    """
                    SELECT count(*) AS rows,
                           count(*) FILTER (WHERE district.enabled) AS enabled,
                           count(DISTINCT district.id) AS ids,
                           count(DISTINCT district.canonical_object_id) AS bindings,
                           count(DISTINCT district.slug) AS slugs,
                           count(DISTINCT district.display_order) AS orders,
                           count(*) FILTER (
                             WHERE object.lifecycle_status='active'
                               AND object.geom IS NOT NULL
                               AND NOT ST_IsEmpty(object.geom)
                               AND ST_IsValid(object.geom)
                               AND ST_SRID(object.geom)=4326
                               AND binding.source_status='present'
                               AND binding.source_object_type='relation'
                           ) AS valid
                    FROM domain.districts AS district
                    JOIN catalog.objects AS object ON object.id=district.canonical_object_id
                    JOIN catalog.object_sources AS binding
                      ON binding.object_id=object.id AND binding.source_id=:source_id
                    """
                ),
                {"source_id": source_id},
            ).one()
        assert first.rows == 18 and first.changed == 18
        assert second.rows == 18 and second.changed == 0
        assert initial == repeated
        assert tuple(quality) == (18, 18, 18, 18, 18, 18, 18)

        district_response = client.get("/api/districts")
        assert district_response.status_code == 200
        district_payload = district_response.json()["districts"]
        assert len(district_payload) == 18
        assert [item["display_order"] for item in district_payload] == list(range(1, 19))
        assert all(len(item["bbox"]) == 4 for item in district_payload)
        assert "geometry" not in district_response.text

        district_ids = [str(item.id) for item in DISTRICT_DEFINITIONS]
        common = {"bbox": "9.99,9.99,10.16,10.06", "categories": category, "limit": 10}
        unfiltered = client.get("/api/map/features", params=common)
        one = client.get(
            "/api/map/features", params={**common, "districts": district_ids[0]}
        )
        two = client.get(
            "/api/map/features",
            params={**common, "districts": ",".join(district_ids[:2])},
        )
        three = client.get(
            "/api/map/features",
            params={**common, "districts": ",".join(district_ids[:3])},
        )
        empty = client.get(
            "/api/map/features", params={**common, "districts": district_ids[-1]}
        )
        assert len(unfiltered.json()["features"]) == 5
        assert {item["id"] for item in one.json()["features"]} == {
            str(feature_ids[0]),
            str(feature_ids[2]),
            str(feature_ids[3]),
        }
        assert len(two.json()["features"]) == 5
        assert len({item["id"] for item in two.json()["features"]}) == 5
        assert three.json() == two.json()
        assert empty.json() == {"type": "FeatureCollection", "features": []}

        limited = client.get("/api/map/features", params={**common, "limit": 4})
        district_limited = client.get(
            "/api/map/features",
            params={**common, "limit": 3, "districts": district_ids[0]},
        )
        assert limited.status_code == 422
        assert limited.json()["detail"]["code"] == "feature_limit_exceeded"
        assert district_limited.status_code == 200

        unknown = client.get(
            "/api/map/features", params={**common, "districts": str(uuid4())}
        )
        assert unknown.status_code == 422
        assert unknown.json()["detail"]["code"] == "unknown_district"
        with engine.begin() as connection:
            connection.execute(
                text("UPDATE domain.districts SET enabled=false WHERE id=:id"),
                {"id": DISTRICT_DEFINITIONS[0].id},
            )
        disabled = client.get(
            "/api/map/features", params={**common, "districts": district_ids[0]}
        )
        assert disabled.status_code == 422
        assert disabled.json()["detail"]["disabled_districts"] == [district_ids[0]]
    finally:
        with engine.begin() as connection:
            connection.execute(text("DELETE FROM domain.districts"))
            connection.execute(
                text("DELETE FROM catalog.object_categories WHERE object_id=ANY(:ids)"),
                {"ids": feature_ids},
            )
            connection.execute(
                text("DELETE FROM catalog.objects WHERE id=ANY(:ids)"),
                {"ids": feature_ids},
            )
            fixture_canonical_ids = list(canonical_ids.values())
            connection.execute(
                text("DELETE FROM catalog.object_sources WHERE object_id=ANY(:ids)"),
                {"ids": fixture_canonical_ids},
            )
            connection.execute(
                text("DELETE FROM catalog.objects WHERE id=ANY(:ids)"),
                {"ids": fixture_canonical_ids},
            )
            connection.execute(
                text("DELETE FROM catalog.categories WHERE key=:category"),
                {"category": category},
            )
            if source_id is not None:
                connection.execute(
                    text("DELETE FROM staging.osm_relation_members WHERE source_id=:source_id"),
                    {"source_id": source_id},
                )
                connection.execute(
                    text("DELETE FROM staging.osm_relations WHERE source_id=:source_id"),
                    {"source_id": source_id},
                )
                connection.execute(
                    text("DELETE FROM meta.import_runs WHERE source_id=:source_id"),
                    {"source_id": source_id},
                )
                connection.execute(
                    text("DELETE FROM meta.dataset_sources WHERE id=:source_id"),
                    {"source_id": source_id},
                )
            if saved_registry:
                connection.execute(
                    text(
                        """
                        INSERT INTO domain.districts
                          (id,canonical_object_id,name,slug,display_order,enabled,
                           created_at,updated_at)
                        VALUES (:id,:canonical_object_id,:name,:slug,:display_order,:enabled,
                                :created_at,:updated_at)
                        """
                    ),
                    saved_registry,
                )
