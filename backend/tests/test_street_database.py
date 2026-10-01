import json
import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text

import app.data.streets as streets


def database_url() -> str:
    value = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL")
    if value is None:
        pytest.skip("Set TEST_DATABASE_URL to run database integration tests")
    return value


@pytest.mark.integration
def test_street_refresh_groups_conservatively_and_is_retry_safe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_engine(database_url())
    token = uuid4().hex[:8]
    object_ids = [uuid4() for _ in range(7)]
    source_id: int | None = None
    run_id: int | None = None
    relation_id = 9001
    names = [
        "Test Main Street",
        "Test Main Street",
        "Test Main Street",
        "Test Main Street",
        "Different Street",
        None,
        "Test Main Street",
    ]
    wkts = [
        "LINESTRING(30 60,30.001 60)",
        "LINESTRING(30.001 60,30.002 60)",
        "LINESTRING(30 60.0001,30.002 60.0001)",
        "LINESTRING(31 60,31.001 60)",
        "LINESTRING(30.002 60,30.003 60)",
        "LINESTRING(30 60.01,30.001 60.01)",
        "LINESTRING(30.003 60,30.004 60)",
    ]
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO catalog.categories (key,label,enabled) "
                    "VALUES ('transport.road','Road',true) ON CONFLICT (key) DO NOTHING"
                )
            )
            source_id = int(
                connection.scalar(
                    text(
                        """
                        INSERT INTO meta.dataset_sources
                          (name,provider,source_type,source_url,version)
                        VALUES (:name,'fixture','fixture','https://example.invalid','v1')
                        RETURNING id
                        """
                    ),
                    {"name": f"street-{token}"},
                )
            )
            run_id = int(
                connection.scalar(
                    text(
                        """
                        INSERT INTO meta.import_runs
                          (source_id,status,source_version,started_at,finished_at)
                        VALUES (:source,'success','v1',now(),now()) RETURNING id
                        """
                    ),
                    {"source": source_id},
                )
            )
            for index, (object_id, name, wkt) in enumerate(
                zip(object_ids, names, wkts, strict=True), start=1
            ):
                tags = {"highway": "residential"}
                if name is not None:
                    tags["name"] = name
                connection.execute(
                    text(
                        """
                        INSERT INTO staging.osm_ways
                          (source_id,osm_id,tags,geom,import_run_id,imported_at)
                        VALUES (:source,:osm_id,CAST(:tags AS jsonb),
                                ST_GeomFromText(:wkt,4326),:run,now())
                        """
                    ),
                    {
                        "source": source_id,
                        "osm_id": index,
                        "tags": json.dumps(tags),
                        "wkt": wkt,
                        "run": run_id,
                    },
                )
                connection.execute(
                    text(
                        """
                        INSERT INTO catalog.objects
                          (id,object_kind,lifecycle_status,name,geom,properties,
                           property_sources,revision)
                        VALUES (:id,'feature','active',:name,
                                ST_GeomFromText(:wkt,4326),'{}','{}',1)
                        """
                    ),
                    {"id": object_id, "name": name, "wkt": wkt},
                )
                connection.execute(
                    text(
                        "INSERT INTO catalog.object_categories "
                        "(object_id,category_key,lifecycle_status) "
                        "VALUES (:id,'transport.road','active')"
                    ),
                    {"id": object_id},
                )
                connection.execute(
                    text(
                        """
                        INSERT INTO catalog.object_sources
                          (object_id,source_id,source_object_type,source_object_id,
                           source_native_version,source_status,candidate_properties,
                           payload_hash,geometry_quality,source_priority,match_method,
                           match_confidence,first_seen_import_run_id,last_seen_import_run_id,
                           last_changed_import_run_id)
                        VALUES (:id,:source,'way',:osm_id,'v1','present','{}',repeat('a',64),
                                'raw',0,'source_identity',1,:run,:run,:run)
                        """
                    ),
                    {
                        "id": object_id,
                        "source": source_id,
                        "osm_id": str(index),
                        "run": run_id,
                    },
                )
            connection.execute(
                text(
                    """
                    INSERT INTO staging.osm_relations
                      (source_id,osm_id,tags,import_run_id,imported_at)
                    VALUES (:source,:relation,CAST(:tags AS jsonb),:run,now())
                    """
                ),
                {
                    "source": source_id,
                    "relation": relation_id,
                    "tags": json.dumps({"type": "street", "name": "Test Main Street"}),
                    "run": run_id,
                },
            )
            for sequence, member_id in enumerate((1, 7)):
                connection.execute(
                    text(
                        """
                        INSERT INTO staging.osm_relation_members
                          (source_id,relation_id,sequence,member_type,member_id,role,
                           import_run_id)
                        VALUES (:source,:relation,:sequence,'way',:member,'street',:run)
                        """
                    ),
                    {
                        "source": source_id,
                        "relation": relation_id,
                        "sequence": sequence,
                        "member": member_id,
                        "run": run_id,
                    },
                )

        with engine.connect() as connection:
            before = connection.execute(
                text(
                    "SELECT (SELECT count(*) FROM catalog.objects),"
                    "(SELECT count(*) FROM catalog.object_categories)"
                )
            ).one()

        dry_run = streets.dry_run_streets(engine=engine)
        assert dry_run.eligible_members == 6
        assert dry_run.street_entities == 3
        assert dry_run.multi_member_entities == 1
        assert dry_run.largest_entity_members == 4
        assert dry_run.separated_same_name_cases == 1
        assert dry_run.relation_supported_entities == 1

        first = streets.refresh_streets(engine=engine)
        assert first.active_entities == 3
        assert first.active_members == 6
        assert first.created_entities == 3
        second = streets.refresh_streets(engine=engine)
        assert second.created_entities == 0
        assert second.changed_entities == 0
        assert second.unchanged_entities == 3

        with engine.connect() as connection:
            after = connection.execute(
                text(
                    "SELECT (SELECT count(*) FROM catalog.objects),"
                    "(SELECT count(*) FROM catalog.object_categories)"
                )
            ).one()
            main_members = int(
                connection.scalar(
                    text(
                        """
                        SELECT max(member_count) FROM (
                          SELECT count(*) AS member_count
                          FROM domain.street_entity_members AS member
                          JOIN domain.street_entities AS entity
                            ON entity.id=member.street_entity_id
                          WHERE entity.search_name='test main street'
                            AND entity.lifecycle_status='active'
                            AND member.lifecycle_status='active'
                          GROUP BY entity.id
                        ) AS grouped
                        """
                    )
                )
            )
        assert after == before
        assert main_members == 4

        original_write = streets._write_plan

        def fail_after_write(*args: object, **kwargs: object) -> None:
            original_write(*args, **kwargs)  # type: ignore[arg-type]
            raise RuntimeError("street fixture failure")

        monkeypatch.setattr(streets, "_write_plan", fail_after_write)
        with pytest.raises(RuntimeError, match="street fixture failure"):
            streets.refresh_streets(engine=engine)
        with engine.connect() as connection:
            assert int(
                connection.scalar(
                    text(
                        "SELECT count(*) FROM domain.street_entities "
                        "WHERE lifecycle_status='active'"
                    )
                )
            ) == 3
    finally:
        monkeypatch.undo()
        with engine.begin() as connection:
            connection.execute(
                text(
                    "DELETE FROM domain.street_entity_members "
                    "WHERE canonical_object_id=ANY(:ids)"
                ),
                {"ids": object_ids},
            )
            connection.execute(
                text(
                    "DELETE FROM domain.street_entities AS entity WHERE NOT EXISTS "
                    "(SELECT 1 FROM domain.street_entity_members AS member "
                    "WHERE member.street_entity_id=entity.id)"
                )
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
                    text(
                        "DELETE FROM staging.osm_relation_members WHERE source_id=:source"
                    ),
                    {"source": source_id},
                )
                connection.execute(
                    text("DELETE FROM staging.osm_relations WHERE source_id=:source"),
                    {"source": source_id},
                )
                connection.execute(
                    text("DELETE FROM staging.osm_ways WHERE source_id=:source"),
                    {"source": source_id},
                )
            if run_id is not None:
                connection.execute(
                    text("DELETE FROM meta.import_runs WHERE id=:run"), {"run": run_id}
                )
            if source_id is not None:
                connection.execute(
                    text("DELETE FROM meta.dataset_sources WHERE id=:source"),
                    {"source": source_id},
                )
