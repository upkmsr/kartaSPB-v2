# ruff: noqa: E501
import json
import os
from uuid import uuid4

import pytest
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import IntegrityError

from app.data.catalog import canonicalize_osm_objects
from app.data.categories import apply_categories, bulk_create_osm_objects


def database_url() -> str:
    value = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL")
    if value is None:
        pytest.skip("Set TEST_DATABASE_URL to run database integration tests")
    return value


def create_source(engine: Engine) -> int:
    with engine.begin() as connection:
        return int(
            connection.scalar(
                text(
                    """
                    INSERT INTO meta.dataset_sources
                        (name, provider, source_type, source_url, version)
                    VALUES (:name, 'test', 'osm_pbf', 'https://example.invalid/test.pbf',
                            'fixture-v1')
                    RETURNING id
                    """
                ),
                {"name": f"catalog-test-{uuid4()}"},
            )
        )


def create_successful_run(engine: Engine, source_id: int) -> int:
    with engine.begin() as connection:
        return int(
            connection.scalar(
                text(
                    """
                    INSERT INTO meta.import_runs
                        (source_id, status, source_version, started_at, finished_at)
                    VALUES (:source_id, 'success', 'fixture-v1', now(), now())
                    RETURNING id
                    """
                ),
                {"source_id": source_id},
            )
        )


def cleanup_source(engine: Engine, source_id: int) -> None:
    with engine.begin() as connection:
        object_ids = (
            connection.execute(
                text("SELECT object_id FROM catalog.object_sources WHERE source_id = :source_id"),
                {"source_id": source_id},
            )
            .scalars()
            .all()
        )
        connection.execute(
            text(
                "DELETE FROM catalog.relationships "
                "WHERE subject_id = ANY(:ids) OR object_id = ANY(:ids)"
            ),
            {"ids": object_ids},
        )
        connection.execute(
            text("DELETE FROM catalog.object_category_sources WHERE object_id = ANY(:ids)"),
            {"ids": object_ids},
        )
        connection.execute(
            text("DELETE FROM catalog.object_categories WHERE object_id = ANY(:ids)"),
            {"ids": object_ids},
        )
        connection.execute(
            text("DELETE FROM catalog.object_sources WHERE source_id = :source_id"),
            {"source_id": source_id},
        )
        if object_ids:
            connection.execute(
                text("DELETE FROM catalog.objects WHERE id = ANY(:ids)"),
                {"ids": object_ids},
            )
        connection.execute(
            text("DELETE FROM derived.osm_relation_geometries WHERE source_id = :source_id"),
            {"source_id": source_id},
        )
        connection.execute(
            text("DELETE FROM staging.osm_relations WHERE source_id = :source_id"),
            {"source_id": source_id},
        )
        connection.execute(
            text("DELETE FROM staging.osm_ways WHERE source_id = :source_id"),
            {"source_id": source_id},
        )
        connection.execute(
            text("DELETE FROM staging.osm_nodes WHERE source_id = :source_id"),
            {"source_id": source_id},
        )
        connection.execute(
            text("DELETE FROM meta.dataset_sources WHERE id = :source_id"),
            {"source_id": source_id},
        )


@pytest.mark.integration
def test_category_provenance_reclassification_and_partial_scope() -> None:
    engine = create_engine(database_url())
    source_id = create_source(engine)
    run_id = create_successful_run(engine, source_id)
    try:
        with engine.begin() as connection:
            connection.execute(
                text("""
                    INSERT INTO staging.osm_nodes
                      (source_id,osm_id,tags,geom,import_run_id,imported_at)
                    VALUES
                      (:source_id,2001,'{"amenity":"pharmacy"}'::jsonb,
                       ST_Point(30,60,4326),:run_id,now()),
                      (:source_id,2002,'{"amenity":"pharmacy","highway":"bus_stop"}'::jsonb,
                       ST_Point(30.1,60.1,4326),:run_id,now())
                """),
                {"source_id": source_id, "run_id": run_id},
            )
        assert bulk_create_osm_objects(
            source_id, run_id, [("node", 2001), ("node", 2002)], engine=engine
        ) == 2
        processed, matches = apply_categories(source_id, run_id, engine=engine)
        assert (processed, matches) == (2, 3)
        with engine.connect() as connection:
            bindings = dict(
                connection.execute(
                    text(
                        "SELECT source_object_id,id FROM catalog.object_sources WHERE source_id=:source_id"
                    ),
                    {"source_id": source_id},
                ).all()
            )
            stable_object_id = connection.scalar(
                text("SELECT object_id FROM catalog.object_sources WHERE id=:id"),
                {"id": bindings["2001"]},
            )
            before = int(
                connection.scalar(
                    text(
                        "SELECT count(*) FROM catalog.object_category_sources WHERE status='active' AND object_source_id=:id"
                    ),
                    {"id": bindings["2002"]},
                )
                or 0
            )
        with engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE staging.osm_nodes SET tags=CAST(:tags AS jsonb) "
                    "WHERE source_id=:source_id AND osm_id=2001"
                ),
                {"source_id": source_id, "tags": json.dumps({"amenity": "cafe"})},
            )
        apply_categories(source_id, run_id, engine=engine, binding_ids=[bindings["2001"]])
        with engine.connect() as connection:
            removed = connection.scalar(
                text(
                    "SELECT status FROM catalog.object_category_sources WHERE object_source_id=:id AND category_key='healthcare.pharmacy'"
                ),
                {"id": bindings["2001"]},
            )
            preserved = int(
                connection.scalar(
                    text(
                        "SELECT count(*) FROM catalog.object_category_sources WHERE status='active' AND object_source_id=:id"
                    ),
                    {"id": bindings["2002"]},
                )
                or 0
            )
            current_object_id = connection.scalar(
                text("SELECT object_id FROM catalog.object_sources WHERE id=:id"),
                {"id": bindings["2001"]},
            )
        assert removed == "inactive"
        assert preserved == before
        assert current_object_id == stable_object_id
    finally:
        cleanup_source(engine, source_id)


@pytest.mark.integration
def test_canonical_identity_lifecycle_geometry_and_route_exclusion() -> None:
    engine = create_engine(database_url())
    source_id = create_source(engine)
    first_run = create_successful_run(engine, source_id)
    identities = [
        ("node", 1001),
        ("way", 1001),
        ("way", 1002),
        ("relation", 1003),
        ("relation", 1004),
        ("relation", 1005),
        ("way", 1006),
    ]
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO staging.osm_nodes
                        (source_id, osm_id, tags, geom, import_run_id, imported_at)
                    VALUES
                        (:source_id, 1001, '{"name":"Fixture point"}'::jsonb,
                         ST_GeomFromText('POINT(30 60)', 4326), :run_id, now())
                    """
                ),
                {"source_id": source_id, "run_id": first_run},
            )
            connection.execute(
                text(
                    """
                    INSERT INTO staging.osm_ways
                        (source_id, osm_id, tags, geom, import_run_id, imported_at)
                    VALUES
                        (:source_id, 1001, '{"name":"Same numeric ID way"}'::jsonb,
                         ST_GeomFromText('LINESTRING(30 60, 30.05 60.05)', 4326),
                         :run_id, now()),
                        (:source_id, 1002, '{"name":"Fixture line"}'::jsonb,
                         ST_GeomFromText('LINESTRING(30 60, 30.1 60.1)', 4326),
                         :run_id, now()),
                        (:source_id, 1006, '{"name":"Invalid polygon"}'::jsonb,
                         ST_GeomFromText('POLYGON((30 60,31 61,31 60,30 61,30 60))',
                                        4326), :run_id, now())
                    """
                ),
                {"source_id": source_id, "run_id": first_run},
            )
            connection.execute(
                text(
                    """
                    INSERT INTO staging.osm_relations
                        (source_id, osm_id, tags, import_run_id, imported_at)
                    VALUES
                        (:source_id, 1003,
                         '{"type":"multipolygon","name":"Fixture area"}'::jsonb,
                         :run_id, now()),
                        (:source_id, 1004,
                         '{"type":"route","route":"bus","name":"Fixture route"}'::jsonb,
                         :run_id, now()),
                        (:source_id, 1005,
                         '{"type":"multipolygon","name":"Partial area"}'::jsonb,
                         :run_id, now())
                    """
                ),
                {"source_id": source_id, "run_id": first_run},
            )
            connection.execute(
                text(
                    """
                    INSERT INTO derived.osm_relation_geometries
                        (source_id, relation_id, relation_type, geometry_kind,
                         assembly_method, assembly_status, diagnostics, geom,
                         import_run_id, assembled_at)
                    VALUES
                        (:source_id, 1003, 'multipolygon', 'area', 'fixture', 'assembled',
                         '{}'::jsonb,
                         ST_GeomFromText('POLYGON((30 60,30.1 60,30.1 60.1,30 60.1,30 60))',
                                        4326), :run_id, now()),
                        (:source_id, 1004, 'route', 'route', 'fixture', 'assembled',
                         '{}'::jsonb,
                         ST_GeomFromText('MULTILINESTRING((30 60,30.1 60.1))', 4326),
                         :run_id, now()),
                        (:source_id, 1005, 'multipolygon', 'area', 'fixture', 'partial',
                         '{}'::jsonb,
                         ST_GeomFromText('POLYGON((30 60,30.1 60,30.1 60.1,30 60.1,30 60))',
                                        4326), :run_id, now())
                    """
                ),
                {"source_id": source_id, "run_id": first_run},
            )

        initial = canonicalize_osm_objects(source_id, first_run, identities, engine=engine)
        assert initial.created == 4
        assert initial.excluded == 3
        with engine.connect() as connection:
            original = connection.execute(
                text(
                    """
                    SELECT binding.source_object_type, binding.source_object_id,
                           binding.object_id, binding.id AS binding_id,
                           binding.last_seen_import_run_id,
                           binding.last_changed_import_run_id,
                           object.revision, object.lifecycle_status,
                           object.geometry_source_id, object.name_source_id,
                           ST_IsValid(object.geom) AS valid
                    FROM catalog.object_sources AS binding
                    JOIN catalog.objects AS object ON object.id = binding.object_id
                    WHERE binding.source_id = :source_id
                    ORDER BY binding.source_object_type, binding.source_object_id
                    """
                ),
                {"source_id": source_id},
            ).all()
        assert len(original) == 4
        assert all(row.revision == 1 and row.valid for row in original)
        assert all(row.geometry_source_id == row.binding_id for row in original)
        assert all(row.name_source_id == row.binding_id for row in original)
        stable_ids = {
            (row.source_object_type, row.source_object_id): row.object_id for row in original
        }
        assert stable_ids[("node", "1001")] != stable_ids[("way", "1001")]

        second_run = create_successful_run(engine, source_id)
        rerun = canonicalize_osm_objects(source_id, second_run, identities, engine=engine)
        assert rerun.created == 0
        assert rerun.changed == 0
        assert rerun.unchanged == 4
        with engine.connect() as connection:
            repeated = connection.execute(
                text(
                    """
                    SELECT source_object_type, source_object_id, object_id,
                           last_seen_import_run_id, last_changed_import_run_id
                    FROM catalog.object_sources WHERE source_id = :source_id
                    """
                ),
                {"source_id": source_id},
            ).all()
            revisions = (
                connection.execute(
                    text(
                        "SELECT revision FROM catalog.objects "
                        "WHERE id IN (SELECT object_id FROM catalog.object_sources "
                        "             WHERE source_id = :source_id)"
                    ),
                    {"source_id": source_id},
                )
                .scalars()
                .all()
            )
        assert {
            (row.source_object_type, row.source_object_id): row.object_id for row in repeated
        } == stable_ids
        assert all(row.last_seen_import_run_id == second_run for row in repeated)
        assert all(row.last_changed_import_run_id == first_run for row in repeated)
        assert revisions == [1, 1, 1, 1]

        third_run = create_successful_run(engine, source_id)
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    UPDATE staging.osm_nodes
                    SET tags = '{"name":"Changed point"}'::jsonb,
                        geom = ST_GeomFromText('POINT(30.2 60.2)', 4326),
                        import_run_id = :run_id
                    WHERE source_id = :source_id AND osm_id = 1001
                    """
                ),
                {"source_id": source_id, "run_id": third_run},
            )
        changed = canonicalize_osm_objects(source_id, third_run, [("node", 1001)], engine=engine)
        assert changed.changed == 1
        with engine.connect() as connection:
            point = connection.execute(
                text(
                    """
                    SELECT binding.object_id, binding.last_changed_import_run_id,
                           object.name, object.revision, object.lifecycle_status
                    FROM catalog.object_sources AS binding
                    JOIN catalog.objects AS object ON object.id = binding.object_id
                    WHERE binding.source_id = :source_id
                      AND binding.source_object_type = 'node'
                      AND binding.source_object_id = '1001'
                    """
                ),
                {"source_id": source_id},
            ).one()
            line_status = connection.scalar(
                text(
                    """
                    SELECT object.lifecycle_status
                    FROM catalog.object_sources AS binding
                    JOIN catalog.objects AS object ON object.id = binding.object_id
                    WHERE binding.source_id = :source_id
                      AND binding.source_object_type = 'way'
                      AND binding.source_object_id = '1002'
                    """
                ),
                {"source_id": source_id},
            )
        assert point.object_id == stable_ids[("node", "1001")]
        assert point.last_changed_import_run_id == third_run
        assert point.name == "Changed point"
        assert point.revision == 2
        assert line_status == "active"

        object_ids = list(stable_ids.values())
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO catalog.relationships
                        (subject_id, relationship_type, object_id, derivation_method,
                         lifecycle_status, properties)
                    VALUES (:subject_id, 'near', :object_id, 'inferred', 'active',
                            '{}'::jsonb)
                    """
                ),
                {"subject_id": object_ids[0], "object_id": object_ids[1]},
            )
            with pytest.raises(IntegrityError), connection.begin_nested():
                connection.execute(
                    text(
                        """
                        INSERT INTO catalog.relationships
                            (subject_id, relationship_type, object_id, derivation_method,
                             lifecycle_status, properties)
                        VALUES (:id, 'self', :id, 'manual', 'active', '{}'::jsonb)
                        """
                    ),
                    {"id": object_ids[0]},
                )
    finally:
        cleanup_source(engine, source_id)
