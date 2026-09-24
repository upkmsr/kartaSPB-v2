import hashlib
import json
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Engine, text

from app.db.session import get_engine

OSM_OBJECT_TYPES = frozenset({"node", "way", "relation"})


@dataclass(frozen=True)
class CanonicalizationResult:
    requested: int
    eligible: int
    created: int
    changed: int
    unchanged: int
    excluded: int


@dataclass(frozen=True)
class _Candidate:
    source_object_type: str
    source_object_id: str
    object_kind: str
    name: str | None
    geom_wkb: bytes
    properties: dict[str, Any]
    geometry_quality: str
    payload_hash: str


def _payload_hash(
    *,
    object_kind: str,
    name: str | None,
    geom_wkb: bytes,
    properties: dict[str, Any],
    geometry_quality: str,
) -> str:
    payload = {
        "object_kind": object_kind,
        "name": name,
        "geometry": geom_wkb.hex(),
        "properties": properties,
        "geometry_quality": geometry_quality,
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _load_candidates(
    connection: Any, source_id: int, identities_json: str
) -> list[_Candidate]:
    rows = connection.execute(
        text(
            """
            WITH requested AS (
                SELECT source_object_type, source_object_id
                FROM jsonb_to_recordset(CAST(:identities AS jsonb))
                     AS item(source_object_type text, source_object_id text)
            ), candidates AS (
                SELECT 'node'::text AS source_object_type,
                       node.osm_id::text AS source_object_id,
                       'feature'::text AS object_kind,
                       node.tags ->> 'name' AS name,
                       node.geom,
                       'raw'::text AS geometry_quality
                FROM requested
                JOIN staging.osm_nodes AS node
                  ON requested.source_object_type = 'node'
                 AND requested.source_object_id = node.osm_id::text
                 AND node.source_id = :source_id
                WHERE node.geom IS NOT NULL
                  AND NOT ST_IsEmpty(node.geom)
                  AND ST_IsValid(node.geom)

                UNION ALL

                SELECT 'way', way.osm_id::text, 'feature', way.tags ->> 'name',
                       way.geom, 'raw'
                FROM requested
                JOIN staging.osm_ways AS way
                  ON requested.source_object_type = 'way'
                 AND requested.source_object_id = way.osm_id::text
                 AND way.source_id = :source_id
                WHERE way.geom IS NOT NULL
                  AND GeometryType(way.geom) IN ('LINESTRING', 'POLYGON')
                  AND NOT ST_IsEmpty(way.geom)
                  AND ST_IsValid(way.geom)

                UNION ALL

                SELECT 'relation', relation.osm_id::text,
                       CASE WHEN geometry.relation_type = 'boundary'
                            THEN 'boundary' ELSE 'feature' END,
                       relation.tags ->> 'name', geometry.geom, 'assembled'
                FROM requested
                JOIN staging.osm_relations AS relation
                  ON requested.source_object_type = 'relation'
                 AND requested.source_object_id = relation.osm_id::text
                 AND relation.source_id = :source_id
                JOIN derived.osm_relation_geometries AS geometry
                  ON geometry.source_id = relation.source_id
                 AND geometry.relation_id = relation.osm_id
                 AND geometry.relation_type IN ('multipolygon', 'boundary')
                 AND geometry.assembly_status = 'assembled'
                WHERE relation.tags ->> 'type' IN ('multipolygon', 'boundary')
                  AND geometry.geom IS NOT NULL
                  AND GeometryType(geometry.geom) IN ('POLYGON', 'MULTIPOLYGON')
                  AND NOT ST_IsEmpty(geometry.geom)
                  AND ST_IsValid(geometry.geom)
            )
            SELECT source_object_type, source_object_id, object_kind, name,
                   ST_AsEWKB(geom) AS geom_wkb, geometry_quality
            FROM candidates
            ORDER BY source_object_type, source_object_id
            """
        ),
        {"source_id": source_id, "identities": identities_json},
    ).all()
    candidates: list[_Candidate] = []
    for row in rows:
        geom_wkb = bytes(row.geom_wkb)
        properties: dict[str, Any] = {}
        candidates.append(
            _Candidate(
                source_object_type=str(row.source_object_type),
                source_object_id=str(row.source_object_id),
                object_kind=str(row.object_kind),
                name=str(row.name) if row.name is not None else None,
                geom_wkb=geom_wkb,
                properties=properties,
                geometry_quality=str(row.geometry_quality),
                payload_hash=_payload_hash(
                    object_kind=str(row.object_kind),
                    name=str(row.name) if row.name is not None else None,
                    geom_wkb=geom_wkb,
                    properties=properties,
                    geometry_quality=str(row.geometry_quality),
                ),
            )
        )
    return candidates


def canonicalize_osm_objects(
    source_id: int,
    import_run_id: int,
    identities: list[tuple[str, int]],
    *,
    engine: Engine | None = None,
) -> CanonicalizationResult:
    """Upsert an explicit OSM identity batch without fuzzy matching or absence deletion."""
    normalized = sorted({(kind, str(object_id)) for kind, object_id in identities})
    invalid_types = {kind for kind, _ in normalized} - OSM_OBJECT_TYPES
    if invalid_types:
        raise ValueError(f"Unsupported OSM object types: {sorted(invalid_types)}")
    if not normalized:
        return CanonicalizationResult(0, 0, 0, 0, 0, 0)

    identities_json = json.dumps(
        [
            {"source_object_type": kind, "source_object_id": object_id}
            for kind, object_id in normalized
        ]
    )
    database = engine or get_engine()
    with database.begin() as connection:
        run = connection.execute(
            text(
                """
                SELECT source.version
                FROM meta.import_runs AS run
                JOIN meta.dataset_sources AS source ON source.id = run.source_id
                WHERE run.id = :run_id
                  AND run.source_id = :source_id
                  AND run.status = 'success'
                """
            ),
            {"run_id": import_run_id, "source_id": source_id},
        ).one_or_none()
        if run is None:
            raise ValueError("Canonicalization requires a successful import run for the source")
        source_version = str(run.version) if run.version is not None else None

        candidates = _load_candidates(connection, source_id, identities_json)
        candidate_keys = [
            {
                "source_object_type": candidate.source_object_type,
                "source_object_id": candidate.source_object_id,
            }
            for candidate in candidates
        ]
        candidate_keys_json = json.dumps(candidate_keys)
        existing_rows = connection.execute(
            text(
                """
                SELECT binding.id, binding.object_id, binding.source_object_type,
                       binding.source_object_id, binding.payload_hash
                FROM catalog.object_sources AS binding
                JOIN jsonb_to_recordset(CAST(:identities AS jsonb))
                     AS item(source_object_type text, source_object_id text)
                  ON item.source_object_type = binding.source_object_type
                 AND item.source_object_id = binding.source_object_id
                WHERE binding.source_id = :source_id
                """
            ),
            {"source_id": source_id, "identities": candidate_keys_json},
        ).all()
        existing = {
            (str(row.source_object_type), str(row.source_object_id)): row
            for row in existing_rows
        }

        new_candidates = [
            candidate
            for candidate in candidates
            if (candidate.source_object_type, candidate.source_object_id) not in existing
        ]
        new_object_ids: dict[tuple[str, str], UUID] = {
            (candidate.source_object_type, candidate.source_object_id): uuid4()
            for candidate in new_candidates
        }
        if new_candidates:
            connection.execute(
                text(
                    """
                    INSERT INTO catalog.objects
                        (id, object_kind, lifecycle_status, name, geom, properties,
                         property_sources, revision, created_at, updated_at)
                    VALUES
                        (:id, :object_kind, 'active', :name,
                         ST_GeomFromEWKB(:geom_wkb), CAST(:properties AS jsonb),
                         '{}'::jsonb, 1, now(), now())
                    """
                ),
                [
                    {
                        "id": new_object_ids[
                            (candidate.source_object_type, candidate.source_object_id)
                        ],
                        "object_kind": candidate.object_kind,
                        "name": candidate.name,
                        "geom_wkb": candidate.geom_wkb,
                        "properties": json.dumps(candidate.properties),
                    }
                    for candidate in new_candidates
                ],
            )
            connection.execute(
                text(
                    """
                    INSERT INTO catalog.object_sources
                        (object_id, source_id, source_object_type, source_object_id,
                         source_native_version, source_status, candidate_name,
                         candidate_geom, candidate_properties, payload_hash,
                         geometry_quality, source_priority, match_method, match_confidence,
                         first_seen_import_run_id, last_seen_import_run_id,
                         last_changed_import_run_id, created_at, updated_at)
                    VALUES
                        (:object_id, :source_id, :source_object_type, :source_object_id,
                         :source_native_version, 'present', :candidate_name,
                         ST_GeomFromEWKB(:geom_wkb), CAST(:candidate_properties AS jsonb),
                         :payload_hash, :geometry_quality, 0, 'source_identity', 1.000,
                         :run_id, :run_id, :run_id, now(), now())
                    """
                ),
                [
                    {
                        "object_id": new_object_ids[
                            (candidate.source_object_type, candidate.source_object_id)
                        ],
                        "source_id": source_id,
                        "source_object_type": candidate.source_object_type,
                        "source_object_id": candidate.source_object_id,
                        "source_native_version": source_version,
                        "candidate_name": candidate.name,
                        "geom_wkb": candidate.geom_wkb,
                        "candidate_properties": json.dumps(candidate.properties),
                        "payload_hash": candidate.payload_hash,
                        "geometry_quality": candidate.geometry_quality,
                        "run_id": import_run_id,
                    }
                    for candidate in new_candidates
                ],
            )

        changed_candidates = [
            candidate
            for candidate in candidates
            if (row := existing.get((candidate.source_object_type, candidate.source_object_id)))
            is not None
            and str(row.payload_hash) != candidate.payload_hash
        ]
        unchanged_candidates = [
            candidate
            for candidate in candidates
            if (row := existing.get((candidate.source_object_type, candidate.source_object_id)))
            is not None
            and str(row.payload_hash) == candidate.payload_hash
        ]
        if changed_candidates:
            connection.execute(
                text(
                    """
                    UPDATE catalog.object_sources
                    SET source_native_version = :source_native_version,
                        source_status = 'present', candidate_name = :candidate_name,
                        candidate_geom = ST_GeomFromEWKB(:geom_wkb),
                        candidate_properties = CAST(:candidate_properties AS jsonb),
                        payload_hash = :payload_hash, geometry_quality = :geometry_quality,
                        last_seen_import_run_id = :run_id,
                        last_changed_import_run_id = :run_id,
                        missing_since = NULL, updated_at = now()
                    WHERE source_id = :source_id
                      AND source_object_type = :source_object_type
                      AND source_object_id = :source_object_id
                    """
                ),
                [
                    {
                        "source_native_version": source_version,
                        "candidate_name": candidate.name,
                        "geom_wkb": candidate.geom_wkb,
                        "candidate_properties": json.dumps(candidate.properties),
                        "payload_hash": candidate.payload_hash,
                        "geometry_quality": candidate.geometry_quality,
                        "run_id": import_run_id,
                        "source_id": source_id,
                        "source_object_type": candidate.source_object_type,
                        "source_object_id": candidate.source_object_id,
                    }
                    for candidate in changed_candidates
                ],
            )
        if unchanged_candidates:
            connection.execute(
                text(
                    """
                    UPDATE catalog.object_sources
                    SET source_native_version = :source_native_version,
                        source_status = 'present', last_seen_import_run_id = :run_id,
                        missing_since = NULL, updated_at = now()
                    WHERE source_id = :source_id
                      AND source_object_type = :source_object_type
                      AND source_object_id = :source_object_id
                    """
                ),
                [
                    {
                        "source_native_version": source_version,
                        "run_id": import_run_id,
                        "source_id": source_id,
                        "source_object_type": candidate.source_object_type,
                        "source_object_id": candidate.source_object_id,
                    }
                    for candidate in unchanged_candidates
                ],
            )

        all_binding_rows = connection.execute(
            text(
                """
                SELECT id, object_id, source_object_type, source_object_id
                FROM catalog.object_sources AS binding
                JOIN jsonb_to_recordset(CAST(:identities AS jsonb))
                     AS item(source_object_type text, source_object_id text)
                  USING (source_object_type, source_object_id)
                WHERE binding.source_id = :source_id
                """
            ),
            {"source_id": source_id, "identities": candidate_keys_json},
        ).all()
        bindings = {
            (str(row.source_object_type), str(row.source_object_id)): row
            for row in all_binding_rows
        }
        if new_candidates:
            connection.execute(
                text(
                    """
                    UPDATE catalog.objects
                    SET name_source_id = :binding_id,
                        geometry_source_id = :binding_id,
                        updated_at = now()
                    WHERE id = :object_id
                    """
                ),
                [
                    {
                        "binding_id": bindings[
                            (candidate.source_object_type, candidate.source_object_id)
                        ].id,
                        "object_id": new_object_ids[
                            (candidate.source_object_type, candidate.source_object_id)
                        ],
                    }
                    for candidate in new_candidates
                ],
            )

        existing_object_ids = sorted(
            {
                str(existing[(candidate.source_object_type, candidate.source_object_id)].object_id)
                for candidate in candidates
                if (candidate.source_object_type, candidate.source_object_id) in existing
            }
        )
        if existing_object_ids:
            connection.execute(
                text(
                    """
                    WITH affected AS (
                        SELECT value::uuid AS object_id
                        FROM jsonb_array_elements_text(CAST(:object_ids AS jsonb))
                    ), geometry_winners AS (
                        SELECT DISTINCT ON (binding.object_id)
                               binding.object_id, binding.id, binding.candidate_geom,
                               binding.candidate_properties,
                               CASE WHEN binding.geometry_quality = 'assembled' THEN 2 ELSE 1 END
                                   AS quality_rank
                        FROM catalog.object_sources AS binding
                        JOIN affected ON affected.object_id = binding.object_id
                        WHERE binding.source_status = 'present'
                          AND binding.candidate_geom IS NOT NULL
                        ORDER BY binding.object_id, binding.source_priority DESC,
                                 quality_rank DESC, binding.last_seen_import_run_id DESC,
                                 binding.id ASC
                    ), name_winners AS (
                        SELECT DISTINCT ON (binding.object_id)
                               binding.object_id, binding.id, binding.candidate_name
                        FROM catalog.object_sources AS binding
                        JOIN affected ON affected.object_id = binding.object_id
                        WHERE binding.source_status = 'present'
                          AND binding.candidate_name IS NOT NULL
                        ORDER BY binding.object_id, binding.source_priority DESC,
                                 binding.last_seen_import_run_id DESC, binding.id ASC
                    ), prepared AS (
                        SELECT object.id,
                               CASE WHEN object.geometry_locked THEN object.geom
                                    ELSE geometry.candidate_geom END AS geom,
                               CASE WHEN object.geometry_locked THEN object.geometry_source_id
                                    ELSE geometry.id END AS geometry_source_id,
                               name.candidate_name AS name,
                               name.id AS name_source_id,
                               geometry.candidate_properties AS properties
                        FROM catalog.objects AS object
                        JOIN geometry_winners AS geometry ON geometry.object_id = object.id
                        LEFT JOIN name_winners AS name ON name.object_id = object.id
                    )
                    UPDATE catalog.objects AS current
                    SET geom = prepared.geom,
                        geometry_source_id = prepared.geometry_source_id,
                        name = prepared.name,
                        name_source_id = prepared.name_source_id,
                        properties = prepared.properties,
                        revision = current.revision + 1,
                        updated_at = now()
                    FROM prepared
                    WHERE current.id = prepared.id
                      AND (current.geom IS DISTINCT FROM prepared.geom
                           OR current.geometry_source_id IS DISTINCT FROM
                              prepared.geometry_source_id
                           OR current.name IS DISTINCT FROM prepared.name
                           OR current.name_source_id IS DISTINCT FROM prepared.name_source_id
                           OR current.properties IS DISTINCT FROM prepared.properties)
                    """
                ),
                {"object_ids": json.dumps(existing_object_ids)},
            )

    return CanonicalizationResult(
        requested=len(normalized),
        eligible=len(candidates),
        created=len(new_candidates),
        changed=len(changed_candidates),
        unchanged=len(unchanged_candidates),
        excluded=len(normalized) - len(candidates),
    )
