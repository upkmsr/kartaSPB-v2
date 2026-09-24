import os
from uuid import uuid4

import pytest
from sqlalchemy import Engine, create_engine, text

from app.data.osm.database import finish_import_run, start_import_run
from app.data.osm.pipeline import _merge_relation_geometries


def database_url() -> str:
    value = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL")
    if value is None:
        pytest.skip("Set TEST_DATABASE_URL to run OSM database integration tests")
    return value


def create_source(engine: Engine) -> int:
    name = f"osm_test_{uuid4().hex}"
    with engine.begin() as connection:
        return int(
            connection.scalar(
                text(
                    """
                    INSERT INTO meta.dataset_sources
                        (name, provider, source_type, source_url, license, attribution)
                    VALUES (:name, 'test', 'osm_pbf', 'https://example.test/data',
                            'ODbL-1.0', '© OpenStreetMap contributors')
                    RETURNING id
                    """
                ),
                {"name": name},
            )
        )


@pytest.mark.integration
def test_import_run_success_and_failure_transitions() -> None:
    engine = create_engine(database_url())
    source_id = create_source(engine)
    try:
        success_id = start_import_run(
            engine,
            source_id=source_id,
            source_version="test-v1",
            checksum="a" * 64,
            details={"region": "fixture"},
        )
        finish_import_run(
            engine,
            success_id,
            status="success",
            processed_count=3,
            inserted_count=3,
            updated_count=0,
        )
        failed_id = start_import_run(
            engine,
            source_id=source_id,
            source_version="test-v1",
            checksum="a" * 64,
            details={"region": "invalid_fixture"},
        )
        finish_import_run(
            engine,
            failed_id,
            status="failed",
            error_count=1,
            details={"error": "invalid PBF"},
        )
        with engine.connect() as connection:
            rows = connection.execute(
                text(
                    "SELECT status, finished_at, error_count FROM meta.import_runs "
                    "WHERE id IN (:success_id, :failed_id) ORDER BY id"
                ),
                {"success_id": success_id, "failed_id": failed_id},
            ).all()
        assert rows[0].status == "success"
        assert rows[0].finished_at is not None
        assert rows[1].status == "failed"
        assert rows[1].error_count == 1
    finally:
        with engine.begin() as connection:
            connection.execute(
                text("DELETE FROM meta.dataset_sources WHERE id = :id"), {"id": source_id}
            )


@pytest.mark.integration
def test_osm_identity_jsonb_duplicate_prevention_and_relation_members() -> None:
    engine = create_engine(database_url())
    source_id = create_source(engine)
    run_id = start_import_run(
        engine,
        source_id=source_id,
        source_version="test-v1",
        checksum="b" * 64,
        details={"region": "fixture"},
    )
    try:
        with engine.begin() as connection:
            for name in ("First", "Updated"):
                connection.execute(
                    text(
                        """
                        INSERT INTO staging.osm_nodes
                            (source_id, osm_id, tags, geom, import_run_id, imported_at)
                        VALUES (:source_id, 101, CAST(:tags AS jsonb),
                                ST_SetSRID(ST_MakePoint(30.3, 59.9), 4326), :run_id, now())
                        ON CONFLICT (source_id, osm_id) DO UPDATE
                        SET tags = EXCLUDED.tags, import_run_id = EXCLUDED.import_run_id
                        """
                    ),
                    {"source_id": source_id, "run_id": run_id, "tags": f'{{"name":"{name}"}}'},
                )
            connection.execute(
                text(
                    """
                    INSERT INTO staging.osm_relations
                        (source_id, osm_id, tags, import_run_id, imported_at)
                    VALUES (:source_id, 202, '{"type":"route"}'::jsonb, :run_id, now())
                    """
                ),
                {"source_id": source_id, "run_id": run_id},
            )
            connection.execute(
                text(
                    """
                    INSERT INTO staging.osm_relation_members
                        (source_id, relation_id, sequence, member_type, member_id, role,
                         import_run_id)
                    VALUES
                        (:source_id, 202, 0, 'node', 101, 'stop', :run_id),
                        (:source_id, 202, 1, 'way', 303, '', :run_id)
                    """
                ),
                {"source_id": source_id, "run_id": run_id},
            )
            node = connection.execute(
                text(
                    "SELECT count(*) count, max(tags->>'name') name, max(ST_SRID(geom)) srid "
                    "FROM staging.osm_nodes WHERE source_id = :source_id AND osm_id = 101"
                ),
                {"source_id": source_id},
            ).one()
            members = connection.execute(
                text(
                    "SELECT sequence, member_type, member_id, role "
                    "FROM staging.osm_relation_members WHERE source_id = :source_id "
                    "ORDER BY sequence"
                ),
                {"source_id": source_id},
            ).all()
            normalized_members = connection.execute(
                text(
                    "SELECT sequence, member_kind, is_resolved "
                    "FROM derived.osm_route_members "
                    "WHERE source_id = :source_id AND relation_id = 202 "
                    "ORDER BY sequence"
                ),
                {"source_id": source_id},
            ).all()
        assert node.count == 1
        assert node.name == "Updated"
        assert node.srid == 4326
        assert [(row.member_type, row.role) for row in members] == [
            ("node", "stop"),
            ("way", ""),
        ]
        assert [(row.member_kind, row.is_resolved) for row in normalized_members] == [
            ("stop_position", True),
            ("path", False),
        ]
    finally:
        with engine.begin() as connection:
            connection.execute(
                text("DELETE FROM staging.osm_relation_members WHERE source_id = :id"),
                {"id": source_id},
            )
            connection.execute(
                text("DELETE FROM staging.osm_nodes WHERE source_id = :id"),
                {"id": source_id},
            )
            connection.execute(
                text("DELETE FROM staging.osm_relations WHERE source_id = :id"),
                {"id": source_id},
            )
            connection.execute(
                text("DELETE FROM meta.dataset_sources WHERE id = :id"), {"id": source_id}
            )


@pytest.mark.integration
def test_route_geometry_excludes_platform_way_and_keeps_ordered_members() -> None:
    engine = create_engine(database_url())
    source_id = create_source(engine)
    run_id = start_import_run(
        engine,
        source_id=source_id,
        source_version="test-v1",
        checksum="c" * 64,
        details={"region": "route_fixture"},
    )
    try:
        with engine.begin() as connection:
            connection.execute(text("DROP TABLE IF EXISTS staging._osm_relations"))
            connection.execute(text("DROP TABLE IF EXISTS derived._osm_relation_geometries"))
            connection.execute(
                text(
                    "CREATE TABLE staging._osm_relations "
                    "(relation_id bigint PRIMARY KEY, tags jsonb NOT NULL)"
                )
            )
            connection.execute(
                text(
                    "CREATE TABLE derived._osm_relation_geometries "
                    "(relation_id bigint PRIMARY KEY, relation_type text NOT NULL, "
                    "geom geometry(Geometry, 4326))"
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO staging.osm_nodes
                        (source_id, osm_id, tags, geom, import_run_id, imported_at)
                    VALUES
                        (:source_id, 401, '{"public_transport":"stop_position"}'::jsonb,
                         ST_SetSRID(ST_Point(30.0, 60.0), 4326), :run_id, now())
                    """
                ),
                {"source_id": source_id, "run_id": run_id},
            )
            connection.execute(
                text(
                    """
                    INSERT INTO staging.osm_ways
                        (source_id, osm_id, tags, geom, import_run_id, imported_at)
                    VALUES
                        (:source_id, 402, '{}'::jsonb,
                         ST_GeomFromText('LINESTRING(30 60, 30.01 60.01)', 4326),
                         :run_id, now()),
                        (:source_id, 403, '{"public_transport":"platform"}'::jsonb,
                         ST_GeomFromText('LINESTRING(31 61, 31.01 61.01)', 4326),
                         :run_id, now())
                    """
                ),
                {"source_id": source_id, "run_id": run_id},
            )
            connection.execute(
                text(
                    """
                    INSERT INTO staging.osm_relations
                        (source_id, osm_id, tags, import_run_id, imported_at)
                    VALUES
                        (:source_id, 404, '{"type":"route","route":"bus"}'::jsonb,
                         :run_id, now())
                    """
                ),
                {"source_id": source_id, "run_id": run_id},
            )
            connection.execute(
                text(
                    """
                    INSERT INTO staging.osm_relation_members
                        (source_id, relation_id, sequence, member_type, member_id, role,
                         import_run_id)
                    VALUES
                        (:source_id, 404, 0, 'node', 401, 'stop', :run_id),
                        (:source_id, 404, 1, 'way', 403, 'platform', :run_id),
                        (:source_id, 404, 2, 'way', 402, '', :run_id)
                    """
                ),
                {"source_id": source_id, "run_id": run_id},
            )
            connection.execute(
                text(
                    "INSERT INTO staging._osm_relations (relation_id, tags) "
                    "VALUES (404, CAST(:tags AS jsonb))"
                ),
                {"tags": '{"type":"route","route":"bus"}'},
            )

            statuses = _merge_relation_geometries(connection, source_id, run_id)
            geometry = connection.execute(
                text(
                    """
                    SELECT assembly_status,
                           diagnostics ->> 'path_members' AS path_members,
                           diagnostics ->> 'platform_members' AS platform_members,
                           ST_NumGeometries(geom) AS components,
                           ST_Intersects(
                               geom,
                               ST_GeomFromText('LINESTRING(31 61, 31.01 61.01)', 4326)
                           ) AS contains_platform
                    FROM derived.osm_relation_geometries
                    WHERE source_id = :source_id AND relation_id = 404
                    """
                ),
                {"source_id": source_id},
            ).one()
            ordered = connection.execute(
                text(
                    "SELECT sequence, member_kind FROM derived.osm_route_members "
                    "WHERE source_id = :source_id AND relation_id = 404 ORDER BY sequence"
                ),
                {"source_id": source_id},
            ).all()

        assert statuses == {"assembled": 1}
        assert geometry.assembly_status == "assembled"
        assert geometry.path_members == "1"
        assert geometry.platform_members == "1"
        assert geometry.components == 1
        assert geometry.contains_platform is False
        assert [(row.sequence, row.member_kind) for row in ordered] == [
            (0, "stop_position"),
            (1, "platform"),
            (2, "path"),
        ]
    finally:
        with engine.begin() as connection:
            connection.execute(text("DROP TABLE IF EXISTS staging._osm_relations"))
            connection.execute(text("DROP TABLE IF EXISTS derived._osm_relation_geometries"))
            connection.execute(
                text("DELETE FROM derived.osm_relation_geometries WHERE source_id = :id"),
                {"id": source_id},
            )
            connection.execute(
                text("DELETE FROM staging.osm_relation_members WHERE source_id = :id"),
                {"id": source_id},
            )
            connection.execute(
                text("DELETE FROM staging.osm_ways WHERE source_id = :id"),
                {"id": source_id},
            )
            connection.execute(
                text("DELETE FROM staging.osm_nodes WHERE source_id = :id"),
                {"id": source_id},
            )
            connection.execute(
                text("DELETE FROM staging.osm_relations WHERE source_id = :id"),
                {"id": source_id},
            )
            connection.execute(
                text("DELETE FROM meta.dataset_sources WHERE id = :id"), {"id": source_id}
            )
