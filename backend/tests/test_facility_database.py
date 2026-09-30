import json
import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text

import app.data.facilities as facilities


def database_url() -> str:
    value = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL")
    if value is None:
        pytest.skip("Set TEST_DATABASE_URL to run database integration tests")
    return value


@pytest.mark.integration
def test_refresh_is_conservative_idempotent_and_lifecycle_safe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_engine(database_url())
    token = uuid4().hex[:8]
    category_keys = [
        "healthcare.clinic",
        "healthcare.hospital",
        "education.school",
    ]
    object_ids = [uuid4() for _ in range(7)]
    source_id: int | None = None
    run_id: int | None = None
    try:
        with engine.begin() as connection:
            connection.execute(
                text("""
                    INSERT INTO catalog.categories (key,label,enabled)
                    VALUES
                      ('healthcare.clinic','Clinic',true),
                      ('healthcare.hospital','Hospital',true),
                      ('education.school','School',true)
                    ON CONFLICT (key) DO NOTHING
                """)
            )
            source_id = int(
                connection.scalar(
                    text("""
                        INSERT INTO meta.dataset_sources
                          (name,provider,source_type,source_url,version)
                        VALUES (:name,'fixture','fixture','https://example.invalid','v1')
                        RETURNING id
                    """),
                    {"name": f"facility-{token}"},
                )
            )
            run_id = int(
                connection.scalar(
                    text("""
                        INSERT INTO meta.import_runs
                          (source_id,status,source_version,started_at,finished_at)
                        VALUES (:source,'success','v1',now(),now()) RETURNING id
                    """),
                    {"source": source_id},
                )
            )
            node_rows = [
                (101, {"amenity": "clinic", "name": "Clinic A", "ref": "A"}, object_ids[0]),
                (201, {"amenity": "hospital", "name": "Hospital B", "ref": "B"}, object_ids[2]),
                (301, {"amenity": "school", "name": "School C", "ref": "C"}, object_ids[4]),
            ]
            for index, (osm_id, tags, _) in enumerate(node_rows):
                connection.execute(
                    text("""
                        INSERT INTO staging.osm_nodes
                          (source_id,osm_id,tags,geom,import_run_id,imported_at)
                        VALUES (:source,:osm_id,CAST(:tags AS jsonb),
                                ST_Point(:x,:y,4326),:run,now())
                    """),
                    {
                        "source": source_id,
                        "osm_id": osm_id,
                        "tags": json.dumps(tags),
                        "x": 30.0 + index,
                        "y": 60.0,
                        "run": run_id,
                    },
                )
            way_rows = [
                (102, {"amenity": "clinic", "name": "Clinic A", "ref": "A"}, object_ids[1], 30.0),
                (
                    202,
                    {"amenity": "hospital", "building": "yes", "ref": "B"},
                    object_ids[3],
                    31.0,
                ),
                (302, {"amenity": "school", "name": "School C", "ref": "C"}, object_ids[5], 32.0),
                (303, {"amenity": "school", "name": "School C", "ref": "C"}, object_ids[6], 32.0),
            ]
            for osm_id, tags, _, x in way_rows:
                connection.execute(
                    text("""
                        INSERT INTO staging.osm_ways
                          (source_id,osm_id,tags,geom,import_run_id,imported_at)
                        VALUES (:source,:osm_id,CAST(:tags AS jsonb),
                                ST_MakeEnvelope(:x - 0.001,59.999,:x + 0.001,60.001,4326),
                                :run,now())
                    """),
                    {
                        "source": source_id,
                        "osm_id": osm_id,
                        "tags": json.dumps(tags),
                        "x": x,
                        "run": run_id,
                    },
                )
            connection.execute(
                text("""
                    INSERT INTO catalog.objects
                      (id,object_kind,lifecycle_status,name,geom,properties,property_sources,revision)
                    VALUES
                      (:o0,'feature','active','Clinic A',ST_Point(30,60,4326),'{}','{}',1),
                      (:o1,'feature','active','Clinic A',
                       ST_MakeEnvelope(29.999,59.999,30.001,60.001,4326),'{}','{}',1),
                      (:o2,'feature','active','Hospital B',ST_Point(31,60,4326),'{}','{}',1),
                      (:o3,'feature','active','Hospital B',
                       ST_MakeEnvelope(30.999,59.999,31.001,60.001,4326),'{}','{}',1),
                      (:o4,'feature','active','School C',ST_Point(32,60,4326),'{}','{}',1),
                      (:o5,'feature','active','School C',
                       ST_MakeEnvelope(31.999,59.999,32.001,60.001,4326),'{}','{}',1),
                      (:o6,'feature','active','School C',
                       ST_MakeEnvelope(31.9995,59.9995,32.0005,60.0005,4326),'{}','{}',1)
                """),
                {f"o{index}": object_id for index, object_id in enumerate(object_ids)},
            )
            connection.execute(
                text("""
                    INSERT INTO catalog.object_categories
                      (object_id,category_key,lifecycle_status)
                    VALUES
                      (:o0,'healthcare.clinic','active'),(:o1,'healthcare.clinic','active'),
                      (:o2,'healthcare.hospital','active'),(:o3,'healthcare.hospital','active'),
                      (:o4,'education.school','active'),(:o5,'education.school','active'),
                      (:o6,'education.school','active')
                """),
                {f"o{index}": object_id for index, object_id in enumerate(object_ids)},
            )
            source_rows = [
                (object_ids[0], "node", "101"),
                (object_ids[1], "way", "102"),
                (object_ids[2], "node", "201"),
                (object_ids[3], "way", "202"),
                (object_ids[4], "node", "301"),
                (object_ids[5], "way", "302"),
                (object_ids[6], "way", "303"),
            ]
            for object_id, source_type, source_object_id in source_rows:
                connection.execute(
                    text("""
                        INSERT INTO catalog.object_sources
                          (object_id,source_id,source_object_type,source_object_id,
                           source_native_version,source_status,candidate_properties,
                           payload_hash,geometry_quality,source_priority,match_method,
                           match_confidence,first_seen_import_run_id,last_seen_import_run_id,
                           last_changed_import_run_id)
                        VALUES
                          (:object_id,:source,:source_type,:source_object_id,'v1','present','{}',
                           repeat('a',64),'raw',0,'source_identity',1,:run,:run,:run)
                    """),
                    {
                        "object_id": object_id,
                        "source": source_id,
                        "source_type": source_type,
                        "source_object_id": source_object_id,
                        "run": run_id,
                    },
                )

        with engine.connect() as connection:
            before = connection.execute(
                text("""
                    SELECT
                      (SELECT count(*) FROM catalog.objects) AS objects,
                      (SELECT count(*) FROM catalog.object_categories) AS assignments
                """)
            ).one()

        dry_run = facilities.dry_run_facilities(engine=engine)
        assert dry_run.candidate_pairs == 4
        assert dry_run.strong_pairs == 4
        assert dry_run.conflicts == 1
        assert len(dry_run.groups) == 2
        assert dry_run.multi_member_groups == 2

        first = facilities.refresh_facilities(engine=engine)
        assert first.active_entities == 2
        assert first.multi_member_entities == 2
        assert first.active_members == 4
        assert first.created_entities == 2
        with engine.connect() as connection:
            entity_ids = tuple(
                connection.execute(
                    text("SELECT id FROM domain.facility_entities ORDER BY id")
                ).scalars()
            )
            building_roles = connection.execute(
                text("""
                    SELECT entity.display_object_id,entity.analysis_object_id
                    FROM domain.facility_entities AS entity
                    WHERE entity.category_key='healthcare.hospital'
                """)
            ).one()
        assert building_roles.display_object_id == object_ids[3]
        assert building_roles.analysis_object_id == object_ids[2]

        second = facilities.refresh_facilities(engine=engine)
        assert second.created_entities == 0
        assert second.changed_entities == 0
        assert second.unchanged_entities == 2
        with engine.connect() as connection:
            assert tuple(
                connection.execute(
                    text("SELECT id FROM domain.facility_entities ORDER BY id")
                ).scalars()
            ) == entity_ids
            after = connection.execute(
                text("""
                    SELECT
                      (SELECT count(*) FROM catalog.objects) AS objects,
                      (SELECT count(*) FROM catalog.object_categories) AS assignments
                """)
            ).one()
        assert after == before

        with engine.begin() as connection:
            connection.execute(
                text("UPDATE catalog.objects SET lifecycle_status='inactive' WHERE id=:id"),
                {"id": object_ids[3]},
            )
            connection.execute(
                text("""
                    UPDATE catalog.object_categories SET lifecycle_status='inactive'
                    WHERE object_id=:id AND category_key='healthcare.hospital'
                """),
                {"id": object_ids[3]},
            )
        fallback = facilities.refresh_facilities(engine=engine)
        assert fallback.active_entities == 2
        with engine.connect() as connection:
            hospital = connection.execute(
                text("""
                    SELECT representative_object_id,display_object_id,analysis_object_id
                    FROM domain.facility_entities
                    WHERE category_key='healthcare.hospital'
                """)
            ).one()
        assert hospital.representative_object_id == object_ids[2]
        assert hospital.display_object_id == object_ids[2]
        assert hospital.analysis_object_id == object_ids[2]

        with engine.begin() as connection:
            connection.execute(
                text("UPDATE catalog.objects SET lifecycle_status='active' WHERE id=:id"),
                {"id": object_ids[3]},
            )
            connection.execute(
                text("UPDATE catalog.objects SET lifecycle_status='inactive' WHERE id=:id"),
                {"id": object_ids[2]},
            )
            connection.execute(
                text("""
                    UPDATE catalog.object_categories SET lifecycle_status='active'
                    WHERE object_id=:id AND category_key='healthcare.hospital'
                """),
                {"id": object_ids[3]},
            )
            connection.execute(
                text("""
                    UPDATE catalog.object_categories SET lifecycle_status='inactive'
                    WHERE object_id=:id AND category_key='healthcare.hospital'
                """),
                {"id": object_ids[2]},
            )
        analysis_fallback = facilities.refresh_facilities(engine=engine)
        assert analysis_fallback.active_entities == 2
        with engine.connect() as connection:
            hospital = connection.execute(
                text("""
                    SELECT representative_object_id,display_object_id,analysis_object_id
                    FROM domain.facility_entities
                    WHERE category_key='healthcare.hospital'
                """)
            ).one()
        assert hospital.representative_object_id == object_ids[3]
        assert hospital.display_object_id == object_ids[3]
        assert hospital.analysis_object_id == object_ids[3]

        with engine.begin() as connection:
            connection.execute(
                text("UPDATE catalog.objects SET lifecycle_status='inactive' WHERE id=:id"),
                {"id": object_ids[3]},
            )
            connection.execute(
                text("""
                    UPDATE catalog.object_categories SET lifecycle_status='inactive'
                    WHERE object_id=:id AND category_key='healthcare.hospital'
                """),
                {"id": object_ids[3]},
            )
        all_inactive = facilities.refresh_facilities(engine=engine)
        assert all_inactive.active_entities == 1
        with engine.connect() as connection:
            hospital = connection.execute(
                text("""
                    SELECT lifecycle_status,representative_object_id,
                           display_object_id,analysis_object_id
                    FROM domain.facility_entities
                    WHERE category_key='healthcare.hospital'
                """)
            ).one()
        assert tuple(hospital) == ("inactive", None, None, None)

        with engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE catalog.objects SET lifecycle_status='active' "
                    "WHERE id=ANY(:ids)"
                ),
                {"ids": [object_ids[2], object_ids[3]]},
            )
            connection.execute(
                text("""
                    UPDATE catalog.object_categories SET lifecycle_status='active'
                    WHERE object_id=ANY(:ids) AND category_key='healthcare.hospital'
                """),
                {"ids": [object_ids[2], object_ids[3]]},
            )
        restored = facilities.refresh_facilities(engine=engine)
        assert restored.active_entities == 2

        original_upsert = facilities._upsert_group

        def fail_after_write(*args: object, **kwargs: object) -> tuple[bool, bool]:
            original_upsert(*args, **kwargs)  # type: ignore[arg-type]
            raise RuntimeError("fixture refresh failure")

        monkeypatch.setattr(facilities, "_upsert_group", fail_after_write)
        with pytest.raises(RuntimeError, match="fixture refresh failure"):
            facilities.refresh_facilities(engine=engine)
        with engine.connect() as connection:
            assert int(
                connection.scalar(
                    text(
                        "SELECT count(*) FROM domain.facility_entities "
                        "WHERE lifecycle_status='active'"
                    )
                )
            ) == 2
    finally:
        monkeypatch.undo()
        with engine.begin() as connection:
            connection.execute(
                text("""
                    DELETE FROM domain.facility_entity_members
                    WHERE canonical_object_id=ANY(:ids)
                """),
                {"ids": object_ids},
            )
            connection.execute(
                text("""
                    DELETE FROM domain.facility_entities AS entity
                    WHERE NOT EXISTS (
                      SELECT 1 FROM domain.facility_entity_members AS member
                      WHERE member.facility_entity_id=entity.id
                    )
                """)
            )
            connection.execute(
                text("DELETE FROM catalog.object_sources WHERE object_id=ANY(:ids)"),
                {"ids": object_ids},
            )
            connection.execute(
                text("DELETE FROM catalog.object_categories WHERE object_id=ANY(:ids)"),
                {"ids": object_ids},
            )
            connection.execute(
                text("DELETE FROM catalog.objects WHERE id=ANY(:ids)"),
                {"ids": object_ids},
            )
            if source_id is not None:
                connection.execute(
                    text("DELETE FROM staging.osm_ways WHERE source_id=:id"), {"id": source_id}
                )
                connection.execute(
                    text("DELETE FROM staging.osm_nodes WHERE source_id=:id"), {"id": source_id}
                )
            if run_id is not None:
                connection.execute(
                    text("DELETE FROM meta.import_runs WHERE id=:id"), {"id": run_id}
                )
            if source_id is not None:
                connection.execute(
                    text("DELETE FROM meta.dataset_sources WHERE id=:id"), {"id": source_id}
                )
            connection.execute(
                text("""
                    DELETE FROM catalog.categories AS category
                    WHERE category.key=ANY(:keys)
                      AND NOT EXISTS (
                        SELECT 1 FROM catalog.object_categories AS assignment
                        WHERE assignment.category_key=category.key
                      )
                """),
                {"keys": category_keys},
            )
