import json
import os
import subprocess
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, cast
from urllib.request import Request, urlopen

from sqlalchemy import URL, Connection, Engine, text

from app.data.osm.config import (
    BboxRegionConfig,
    RegionConfig,
    RelationPolygonRegionConfig,
    RelationRegionConfig,
    SourceConfig,
    load_region,
    load_regions,
    load_source,
    project_root,
)
from app.data.osm.database import (
    ensure_source,
    finish_import_run,
    record_download,
    stage_import_run,
    start_import_run,
)
from app.data.osm.files import download_atomic, file_matches_sha256, sha256_file
from app.db.session import get_engine

WORK_TABLES = (
    "derived._osm_relation_geometries",
    "staging._osm_relation_members",
    "staging._osm_relations",
    "staging._osm_ways",
    "staging._osm_nodes",
)


@dataclass(frozen=True)
class RemoteMetadata:
    updated_at: datetime | None
    version: str | None
    content_length: int | None


def run_command(command: list[str], *, env: dict[str, str] | None = None) -> None:
    print("+", " ".join(command), flush=True)
    subprocess.run(command, check=True, env=env)


def run_command_allowing_status(
    command: list[str], *, allowed_statuses: frozenset[int]
) -> int:
    print("+", " ".join(command), flush=True)
    result = subprocess.run(command, check=False)
    if result.returncode not in allowed_statuses:
        raise subprocess.CalledProcessError(result.returncode, command)
    return result.returncode


def validate_pbf(path: Path) -> None:
    run_command(["osmium", "fileinfo", "--input-format", "pbf", "--extended", str(path)])


def remote_metadata(url: str) -> RemoteMetadata:
    request = Request(url, method="HEAD", headers={"User-Agent": "KARTASPB-v2/1.0"})
    with urlopen(request, timeout=30) as response:
        last_modified = response.headers.get("Last-Modified")
        updated_at = parsedate_to_datetime(last_modified) if last_modified else None
        if updated_at and updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=UTC)
        version = updated_at.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ") if updated_at else None
        raw_length = response.headers.get("Content-Length")
        return RemoteMetadata(
            updated_at=updated_at,
            version=version,
            content_length=int(raw_length) if raw_length else None,
        )


def provider_md5(url: str | None) -> str | None:
    if not url:
        return None
    request = Request(url, headers={"User-Agent": "KARTASPB-v2/1.0"})
    with urlopen(request, timeout=30) as response:
        first_token = cast(str, response.read().decode("ascii").strip().split()[0])
    if len(first_token) != 32:
        raise ValueError("Provider checksum response does not contain a valid MD5")
    return first_token.lower()


def _relative_to_root(path: Path, root: Path) -> str:
    return str(path.resolve().relative_to(root.resolve()))


def download_source(*, force: bool = False, engine: Engine | None = None) -> Path:
    root = project_root()
    source = load_source(root)
    database = engine or get_engine()
    metadata = remote_metadata(source.source_url)

    with database.begin() as connection:
        row = ensure_source(connection, source)

    previous_version = str(row["version"]) if row["version"] else None
    previous_filename = str(row["local_filename"]) if row["local_filename"] else None
    previous_checksum = str(row["checksum"]) if row["checksum"] else None
    version = metadata.version or previous_version or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")

    if not force and previous_version == version and previous_filename and previous_checksum:
        existing = root / previous_filename
        if file_matches_sha256(existing, previous_checksum):
            print(f"Source already current: {existing} ({previous_checksum})")
            return existing

    destination = root / "data/sources/osm" / f"northwestern-fed-district-{version}.osm.pbf"
    expected_md5 = provider_md5(source.checksum_url)
    checksum, size = download_atomic(
        source.source_url,
        destination,
        expected_md5=expected_md5,
        validator=validate_pbf,
    )
    with database.begin() as connection:
        current = ensure_source(connection, source)
        record_download(
            connection,
            int(current["id"]),
            version=version,
            checksum=checksum,
            local_filename=_relative_to_root(destination, root),
            source_updated_at=metadata.updated_at,
        )
    print(f"Downloaded {size} bytes to {destination}")
    print(f"SHA-256: {checksum}")
    return destination


def _registered_source(connection: Connection, source: SourceConfig) -> dict[str, Any]:
    row = ensure_source(connection, source)
    if not row["local_filename"] or not row["checksum"]:
        raise RuntimeError("OSM source has not been downloaded; run the download command first")
    return dict(row)


def _extract_command(
    region: RegionConfig,
    source_file: Path,
    partial: Path,
    *,
    polygon_file: Path | None = None,
) -> list[str]:
    if isinstance(region, BboxRegionConfig):
        bbox = ",".join(str(value) for value in region.bbox)
        return [
            "osmium",
            "extract",
            "--bbox",
            bbox,
            "--strategy",
            "simple",
            "--output",
            str(partial),
            "--output-format",
            "pbf",
            str(source_file),
        ]
    if isinstance(region, RelationRegionConfig):
        return [
            "osmium",
            "getid",
            "--add-referenced",
            "--verbose-ids",
            "--output-format",
            "pbf",
            "--output",
            str(partial),
            str(source_file),
            *(f"r{relation_id}" for relation_id in region.relation_ids),
        ]
    if isinstance(region, RelationPolygonRegionConfig):
        if polygon_file is None:
            raise ValueError("relation_polygon extraction requires a generated polygon file")
        return [
            "osmium",
            "extract",
            "--polygon",
            str(polygon_file),
            "--strategy",
            "simple",
            "--output",
            str(partial),
            "--output-format",
            "pbf",
            str(source_file),
        ]
    raise TypeError(f"Unsupported OSM region profile: {type(region).__name__}")


def _relation_polygon_files(partial: Path) -> tuple[Path, Path, Path]:
    prefix = partial.with_name(f"{partial.name}.scope")
    return (
        prefix.with_suffix(".osm.pbf"),
        prefix.with_suffix(".geojsonseq"),
        prefix.with_suffix(".geojson"),
    )


def _complete_relation_polygon_selection(
    source_file: Path, selection: Path, partial: Path
) -> tuple[Path, ...]:
    way_ids = selection.with_name(f"{selection.name}.ways.osm.pbf")
    relation_ids = selection.with_name(f"{selection.name}.relations.osm.pbf")
    parent_candidates = selection.with_name(f"{selection.name}.parent-candidates.osm.pbf")
    parent_ids = selection.with_name(f"{selection.name}.route-masters.osm.pbf")
    reference_ids = selection.with_name(f"{selection.name}.reference-ids.osm.pbf")
    closure = selection.with_name(f"{selection.name}.closure.osm.pbf")
    for path in (
        way_ids,
        relation_ids,
        parent_candidates,
        parent_ids,
        reference_ids,
        closure,
        partial,
    ):
        path.unlink(missing_ok=True)
    run_command(
        [
            "osmium",
            "cat",
            "--object-type",
            "way",
            "--output-format",
            "pbf",
            "--output",
            str(way_ids),
            str(selection),
        ]
    )
    run_command(
        [
            "osmium",
            "tags-filter",
            "--omit-referenced",
            "--output-format",
            "pbf",
            "--output",
            str(relation_ids),
            str(selection),
            "r/type=multipolygon,boundary,route,route_master",
        ]
    )
    run_command(
        [
            "osmium",
            "getparents",
            "--add-self",
            "--id-osm-file",
            str(relation_ids),
            "--output-format",
            "pbf",
            "--output",
            str(parent_candidates),
            str(source_file),
        ]
    )
    run_command(
        [
            "osmium",
            "tags-filter",
            "--omit-referenced",
            "--output-format",
            "pbf",
            "--output",
            str(parent_ids),
            str(parent_candidates),
            "r/type=route_master",
        ]
    )
    run_command(
        [
            "osmium",
            "merge",
            str(way_ids),
            str(relation_ids),
            str(parent_ids),
            "--output-format",
            "pbf",
            "--output",
            str(reference_ids),
        ]
    )
    closure_status = run_command_allowing_status(
        [
            "osmium",
            "getid",
            "--add-referenced",
            "--id-osm-file",
            str(reference_ids),
            "--output-format",
            "pbf",
            "--output",
            str(closure),
            str(source_file),
        ],
        allowed_statuses=frozenset({0, 1}),
    )
    if closure_status == 1:
        print(
            "Warning: source-region PBF lacks some externally referenced relation members; "
            "the extract will retain all references available in the locked source.",
            flush=True,
        )
    run_command(
        [
            "osmium",
            "merge",
            str(selection),
            str(closure),
            "--output-format",
            "pbf",
            "--output",
            str(partial),
        ]
    )
    return (
        way_ids,
        relation_ids,
        parent_candidates,
        parent_ids,
        reference_ids,
        closure,
    )


def _build_relation_polygon(
    region: RelationPolygonRegionConfig, source_file: Path, partial: Path
) -> tuple[Path, tuple[Path, ...]]:
    boundary_pbf, sequence_file, polygon_file = _relation_polygon_files(partial)
    temporary = (boundary_pbf, sequence_file, polygon_file)
    for path in temporary:
        path.unlink(missing_ok=True)
    run_command(
        [
            "osmium",
            "getid",
            "--add-referenced",
            "--verbose-ids",
            "--output-format",
            "pbf",
            "--output",
            str(boundary_pbf),
            str(source_file),
            f"r{region.relation_id}",
        ]
    )
    run_command(
        [
            "osmium",
            "export",
            "--geometry-types",
            "polygon",
            "--attributes",
            "id,type",
            "--output-format",
            "geojsonseq",
            "--output",
            str(sequence_file),
            str(boundary_pbf),
        ]
    )
    matches: list[dict[str, Any]] = []
    with sequence_file.open(encoding="utf-8") as source:
        for raw_line in source:
            line = raw_line.lstrip("\x1e").strip()
            if not line:
                continue
            feature = json.loads(line)
            properties = feature.get("properties", {})
            if (
                properties.get("@type") == "relation"
                and str(properties.get("@id")) == str(region.relation_id)
            ):
                matches.append(feature)
    if len(matches) != 1 or not matches[0].get("geometry"):
        raise ValueError(
            f"Expected exactly one polygon geometry for OSM relation {region.relation_id}"
        )
    scope = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "source": "openstreetmap",
                    "osm_type": "relation",
                    "osm_id": region.relation_id,
                },
                "geometry": matches[0]["geometry"],
            }
        ],
    }
    polygon_file.write_text(
        json.dumps(scope, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    return polygon_file, temporary


def _extract_metadata(
    region: RelationPolygonRegionConfig, source: dict[str, Any]
) -> dict[str, Any]:
    return {
        "profile": asdict(region),
        "source_version": str(source["version"]),
        "source_checksum": str(source["checksum"]),
    }


def extract_region(region_name: str, *, force: bool = False, engine: Engine | None = None) -> Path:
    root = project_root()
    source_config = load_source(root)
    region = load_region(region_name, root)
    database = engine or get_engine()
    with database.begin() as connection:
        source = _registered_source(connection, source_config)

    source_file = root / str(source["local_filename"])
    if not source_file.is_file():
        raise FileNotFoundError(f"Registered source file is missing: {source_file}")
    if sha256_file(source_file) != source["checksum"]:
        raise ValueError("Registered source file SHA-256 does not match metadata")
    if isinstance(region, RelationPolygonRegionConfig) and (
        str(source["version"]) != region.source_version
        or str(source["checksum"]) != region.source_checksum
    ):
        raise ValueError(
            f"Region {region.name!r} is locked to source {region.source_version} "
            f"({region.source_checksum})"
        )

    version = str(source["version"])
    output = root / "data/cache/osm" / version / f"{region.name}.osm.pbf"
    checksum_file = output.with_suffix(f"{output.suffix}.sha256")
    metadata_file = output.with_suffix(f"{output.suffix}.metadata.json")
    if not force and output.is_file() and checksum_file.is_file():
        recorded = checksum_file.read_text(encoding="ascii").strip()
        metadata_matches = True
        if isinstance(region, RelationPolygonRegionConfig):
            metadata_matches = bool(
                metadata_file.is_file()
                and json.loads(metadata_file.read_text(encoding="utf-8"))
                == _extract_metadata(region, source)
            )
        if recorded and sha256_file(output) == recorded and metadata_matches:
            print(f"Extract already current: {output} ({recorded})")
            return output

    output.parent.mkdir(parents=True, exist_ok=True)
    partial = output.with_name(f"{output.name}.part")
    partial.unlink(missing_ok=True)
    temporary: tuple[Path, ...] = ()
    try:
        polygon_file = None
        if isinstance(region, RelationPolygonRegionConfig):
            polygon_file, temporary = _build_relation_polygon(region, source_file, partial)
        if isinstance(region, RelationPolygonRegionConfig):
            selection = partial.with_name(f"{partial.name}.selection.osm.pbf")
            selection.unlink(missing_ok=True)
            temporary = (*temporary, selection)
            run_command(
                _extract_command(region, source_file, selection, polygon_file=polygon_file)
            )
            closure_files = _complete_relation_polygon_selection(
                source_file, selection, partial
            )
            temporary = (*temporary, *closure_files)
        else:
            run_command(_extract_command(region, source_file, partial))
        validate_pbf(partial)
        checksum = sha256_file(partial)
        partial.replace(output)
        checksum_file.write_text(f"{checksum}\n", encoding="ascii")
        if isinstance(region, RelationPolygonRegionConfig):
            metadata_file.write_text(
                json.dumps(_extract_metadata(region, source), indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
    except BaseException:
        partial.unlink(missing_ok=True)
        raise
    finally:
        for path in temporary:
            path.unlink(missing_ok=True)
    print(f"Created {region.name} extract: {output}")
    print(f"SHA-256: {checksum}")
    return output


def _osm2pgsql_connection(database_url: URL) -> tuple[list[str], dict[str, str]]:
    if not database_url.host or not database_url.database:
        raise ValueError("DATABASE_URL must include a host and database name")
    arguments = [
        f"--host={database_url.host}",
        f"--port={database_url.port or 5432}",
        f"--database={database_url.database}",
    ]
    if database_url.username:
        arguments.append(f"--username={database_url.username}")
    environment = os.environ.copy()
    if database_url.password:
        environment["PGPASSWORD"] = database_url.password
    return arguments, environment


def _cleanup_work_tables(engine: Engine) -> None:
    with engine.begin() as connection:
        for table in WORK_TABLES:
            connection.execute(text(f"DROP TABLE IF EXISTS {table} CASCADE"))


def _work_count(connection: Connection, table: str) -> int:
    return int(connection.scalar(text(f"SELECT count(*) FROM {table}")) or 0)


def _new_count(
    connection: Connection, work: str, target: str, id_column: str, source_id: int
) -> int:
    return int(
        connection.scalar(
            text(
                f"""
                SELECT count(*)
                FROM {work} work
                LEFT JOIN {target} target
                  ON target.source_id = :source_id
                 AND target.osm_id = work.{id_column}
                WHERE target.osm_id IS NULL
                """
            ),
            {"source_id": source_id},
        )
        or 0
    )


def _changed_count(
    connection: Connection,
    work: str,
    target: str,
    id_column: str,
    source_id: int,
    *,
    include_geometry: bool,
) -> int:
    geometry_difference = "OR target.geom IS DISTINCT FROM work.geom" if include_geometry else ""
    return int(
        connection.scalar(
            text(
                f"""
                SELECT count(*)
                FROM {work} work
                JOIN {target} target
                  ON target.source_id = :source_id
                 AND target.osm_id = work.{id_column}
                WHERE target.tags IS DISTINCT FROM COALESCE(work.tags, '{{}}'::jsonb)
                   {geometry_difference}
                """
            ),
            {"source_id": source_id},
        )
        or 0
    )


def _merge_work_tables(connection: Connection, source_id: int, run_id: int) -> dict[str, int]:
    connection.execute(
        text("DELETE FROM staging.osm_nodes WHERE source_id = :source_id AND tags = '{}'::jsonb"),
        {"source_id": source_id},
    )
    specs = (
        ("node", "staging._osm_nodes", "staging.osm_nodes", "node_id"),
        ("way", "staging._osm_ways", "staging.osm_ways", "way_id"),
        ("relation", "staging._osm_relations", "staging.osm_relations", "relation_id"),
    )
    counts: dict[str, int] = {}
    inserted = 0
    updated = 0
    for object_type, work, target, id_column in specs:
        counts[f"{object_type}s"] = _work_count(connection, work)
        inserted += _new_count(connection, work, target, id_column, source_id)
        updated += _changed_count(
            connection,
            work,
            target,
            id_column,
            source_id,
            include_geometry=object_type != "relation",
        )
        geometry_select = "NULL" if object_type == "relation" else "work.geom"
        geometry_difference = (
            "OR current.geom IS DISTINCT FROM EXCLUDED.geom" if object_type != "relation" else ""
        )
        connection.execute(
            text(
                f"""
                INSERT INTO {target} AS current
                    (source_id, osm_id, osm_type, tags, geom, import_run_id, imported_at)
                SELECT :source_id, work.{id_column}, :object_type,
                       COALESCE(work.tags, '{{}}'::jsonb), {geometry_select}, :run_id, now()
                FROM {work} work
                ON CONFLICT (source_id, osm_id) DO UPDATE SET
                    tags = EXCLUDED.tags,
                    geom = EXCLUDED.geom,
                    import_run_id = EXCLUDED.import_run_id,
                    imported_at = EXCLUDED.imported_at
                WHERE current.tags IS DISTINCT FROM EXCLUDED.tags
                   {geometry_difference}
                """
            ),
            {"source_id": source_id, "object_type": object_type, "run_id": run_id},
        )

    connection.execute(
        text(
            """
            DELETE FROM staging.osm_relation_members members
            USING staging._osm_relations relations
            WHERE members.source_id = :source_id
              AND members.relation_id = relations.relation_id
            """
        ),
        {"source_id": source_id},
    )
    connection.execute(
        text(
            """
            INSERT INTO staging.osm_relation_members
                (source_id, relation_id, sequence, member_type, member_id, role, import_run_id)
            SELECT :source_id, relation_id, sequence, member_type, member_id,
                   COALESCE(role, ''), :run_id
            FROM staging._osm_relation_members
            ON CONFLICT (source_id, relation_id, sequence) DO UPDATE SET
                member_type = EXCLUDED.member_type,
                member_id = EXCLUDED.member_id,
                role = EXCLUDED.role,
                import_run_id = EXCLUDED.import_run_id
            """
        ),
        {"source_id": source_id, "run_id": run_id},
    )
    counts["relation_members"] = _work_count(connection, "staging._osm_relation_members")
    counts["processed"] = counts["nodes"] + counts["ways"] + counts["relations"]
    counts["inserted"] = inserted
    counts["updated"] = updated
    counts["skipped"] = counts["processed"] - inserted - updated
    return counts


def _record_profile_memberships(
    connection: Connection, source_id: int, profile: str, run_id: int
) -> None:
    """Record scope observation separately from the global OSM staging identity."""
    for object_type, work, id_column in (
        ("node", "staging._osm_nodes", "node_id"),
        ("way", "staging._osm_ways", "way_id"),
        ("relation", "staging._osm_relations", "relation_id"),
    ):
        connection.execute(
            text(
                f"""
                INSERT INTO meta.osm_profile_memberships AS membership
                    (source_id, profile, source_object_type, source_object_id,
                     lifecycle_status, first_seen_import_run_id,
                     last_seen_import_run_id, missing_since, created_at, updated_at)
                SELECT :source_id, :profile, :object_type, work.{id_column}, 'present',
                       :run_id, :run_id, NULL, now(), now()
                FROM {work} AS work
                ON CONFLICT (source_id, profile, source_object_type, source_object_id)
                DO UPDATE SET lifecycle_status = 'present',
                              last_seen_import_run_id = EXCLUDED.last_seen_import_run_id,
                              missing_since = NULL,
                              updated_at = now()
                """
            ),
            {
                "source_id": source_id,
                "profile": profile,
                "object_type": object_type,
                "run_id": run_id,
            },
        )


def _merge_relation_geometries(
    connection: Connection, source_id: int, run_id: int
) -> dict[str, int]:
    """Build source-specific GIS interpretations without changing raw staging."""
    parameters = {"source_id": source_id, "run_id": run_id}
    connection.execute(
        text(
            """
            DELETE FROM derived.osm_relation_geometries AS geometry
            USING staging._osm_relations AS work
            WHERE geometry.source_id = :source_id
              AND geometry.relation_id = work.relation_id
              AND COALESCE(work.tags ->> 'type', '')
                  NOT IN ('multipolygon', 'boundary', 'route')
            """
        ),
        parameters,
    )
    connection.execute(
        text(
            """
            WITH area_rows AS (
                SELECT
                    work.relation_id,
                    work.relation_type,
                    work.geom,
                    members.member_count,
                    members.way_members,
                    members.missing_way_members,
                    members.null_way_geometries,
                    members.nested_relation_members,
                    members.geometry_relation_members,
                    members.missing_relation_members
                FROM derived._osm_relation_geometries AS work
                CROSS JOIN LATERAL (
                    SELECT
                        count(*) AS member_count,
                        count(*) FILTER (
                            WHERE member.member_type = 'way'
                        ) AS way_members,
                        count(*) FILTER (
                            WHERE member.member_type = 'way'
                              AND way.osm_id IS NULL
                        ) AS missing_way_members,
                        count(*) FILTER (
                            WHERE member.member_type = 'way'
                              AND way.osm_id IS NOT NULL
                              AND way.geom IS NULL
                        ) AS null_way_geometries,
                        count(*) FILTER (
                            WHERE member.member_type = 'relation'
                        ) AS nested_relation_members,
                        count(*) FILTER (
                            WHERE member.member_type = 'relation'
                              AND member.role IN ('', 'outer', 'inner')
                        ) AS geometry_relation_members,
                        count(*) FILTER (
                            WHERE member.member_type = 'relation'
                              AND child.osm_id IS NULL
                        ) AS missing_relation_members
                    FROM staging.osm_relation_members AS member
                    LEFT JOIN staging.osm_ways AS way
                      ON member.member_type = 'way'
                     AND way.source_id = member.source_id
                     AND way.osm_id = member.member_id
                    LEFT JOIN staging.osm_relations AS child
                      ON member.member_type = 'relation'
                     AND child.source_id = member.source_id
                     AND child.osm_id = member.member_id
                    WHERE member.source_id = :source_id
                      AND member.relation_id = work.relation_id
                ) AS members
            ), prepared AS (
                SELECT
                    :source_id AS source_id,
                    relation_id,
                    relation_type,
                    'area' AS geometry_kind,
                    'osm2pgsql_as_multipolygon' AS assembly_method,
                    CASE
                        WHEN geometry_relation_members > 0 THEN 'unsupported_nested'
                        WHEN missing_way_members > 0 OR null_way_geometries > 0
                            THEN CASE WHEN geom IS NULL THEN 'incomplete' ELSE 'partial' END
                        WHEN geom IS NULL THEN 'invalid'
                        WHEN NOT ST_IsValid(geom) THEN 'invalid'
                        ELSE 'assembled'
                    END AS assembly_status,
                    jsonb_build_object(
                        'member_count', member_count,
                        'way_members', way_members,
                        'missing_way_members', missing_way_members,
                        'null_way_geometries', null_way_geometries,
                        'nested_relation_members', nested_relation_members,
                        'geometry_relation_members', geometry_relation_members,
                        'missing_relation_members', missing_relation_members,
                        'assembler', 'osm2pgsql/libosmium',
                        'geometry_type', GeometryType(geom),
                        'is_valid', CASE WHEN geom IS NULL THEN NULL ELSE ST_IsValid(geom) END
                    ) AS diagnostics,
                    geom,
                    :run_id AS import_run_id
                FROM area_rows
            )
            INSERT INTO derived.osm_relation_geometries AS current
                (source_id, relation_id, relation_type, geometry_kind, assembly_method,
                 assembly_status, diagnostics, geom, import_run_id, assembled_at)
            SELECT source_id, relation_id, relation_type, geometry_kind, assembly_method,
                   assembly_status, diagnostics, geom, import_run_id, now()
            FROM prepared
            ON CONFLICT (source_id, relation_id) DO UPDATE SET
                relation_type = EXCLUDED.relation_type,
                geometry_kind = EXCLUDED.geometry_kind,
                assembly_method = EXCLUDED.assembly_method,
                assembly_status = EXCLUDED.assembly_status,
                diagnostics = EXCLUDED.diagnostics,
                geom = EXCLUDED.geom,
                import_run_id = EXCLUDED.import_run_id,
                assembled_at = EXCLUDED.assembled_at
            """
        ),
        parameters,
    )
    connection.execute(
        text(
            """
            WITH route_rows AS (
                SELECT
                    work.relation_id,
                    members.member_count,
                    members.path_members,
                    members.present_path_geometries,
                    members.missing_path_members,
                    members.null_path_geometries,
                    members.stop_members,
                    members.platform_members,
                    members.unresolved_stop_members,
                    members.unresolved_platform_members,
                    members.nested_relation_members,
                    CASE
                        WHEN members.present_path_geometries = 0 THEN NULL
                        ELSE ST_Multi(
                            ST_CollectionExtract(
                                ST_LineMerge(
                                    ST_UnaryUnion(members.path_collection)
                                ),
                                2
                            )
                        )
                    END AS geom
                FROM staging._osm_relations AS work
                CROSS JOIN LATERAL (
                    SELECT
                        count(*) AS member_count,
                        count(*) FILTER (
                            WHERE member.member_type = 'way'
                              AND member.role NOT LIKE 'platform%'
                        ) AS path_members,
                        count(*) FILTER (
                            WHERE member.member_type = 'way'
                              AND member.role NOT LIKE 'platform%'
                              AND way.geom IS NOT NULL
                        ) AS present_path_geometries,
                        count(*) FILTER (
                            WHERE member.member_type = 'way'
                              AND member.role NOT LIKE 'platform%'
                              AND way.osm_id IS NULL
                        ) AS missing_path_members,
                        count(*) FILTER (
                            WHERE member.member_type = 'way'
                              AND member.role NOT LIKE 'platform%'
                              AND way.osm_id IS NOT NULL
                              AND way.geom IS NULL
                        ) AS null_path_geometries,
                        count(*) FILTER (
                            WHERE member.role LIKE 'stop%'
                        ) AS stop_members,
                        count(*) FILTER (
                            WHERE member.role LIKE 'platform%'
                        ) AS platform_members,
                        count(*) FILTER (
                            WHERE member.role LIKE 'stop%'
                              AND node.osm_id IS NULL
                        ) AS unresolved_stop_members,
                        count(*) FILTER (
                            WHERE member.role LIKE 'platform%'
                              AND CASE member.member_type
                                  WHEN 'node' THEN node.osm_id
                                  WHEN 'way' THEN way.osm_id
                                  WHEN 'relation' THEN child.osm_id
                              END IS NULL
                        ) AS unresolved_platform_members,
                        count(*) FILTER (
                            WHERE member.member_type = 'relation'
                        ) AS nested_relation_members,
                        ST_Collect(
                            CASE
                                WHEN member.member_type = 'way'
                                 AND member.role NOT LIKE 'platform%'
                                 AND way.geom IS NOT NULL
                                    THEN CASE
                                        WHEN GeometryType(way.geom) IN
                                             ('POLYGON', 'MULTIPOLYGON')
                                            THEN ST_Boundary(way.geom)
                                        ELSE way.geom
                                    END
                            END
                            ORDER BY member.sequence
                        ) AS path_collection
                    FROM staging.osm_relation_members AS member
                    LEFT JOIN staging.osm_nodes AS node
                      ON member.member_type = 'node'
                     AND node.source_id = member.source_id
                     AND node.osm_id = member.member_id
                    LEFT JOIN staging.osm_ways AS way
                      ON member.member_type = 'way'
                     AND way.source_id = member.source_id
                     AND way.osm_id = member.member_id
                    LEFT JOIN staging.osm_relations AS child
                      ON member.member_type = 'relation'
                     AND child.source_id = member.source_id
                     AND child.osm_id = member.member_id
                    WHERE member.source_id = :source_id
                      AND member.relation_id = work.relation_id
                ) AS members
                WHERE work.tags ->> 'type' = 'route'
            ), prepared AS (
                SELECT
                    :source_id AS source_id,
                    relation_id,
                    'route' AS relation_type,
                    'route' AS geometry_kind,
                    'postgis_unary_union_line_merge' AS assembly_method,
                    CASE
                        WHEN path_members = 0 THEN 'incomplete'
                        WHEN missing_path_members > 0 OR null_path_geometries > 0
                            THEN CASE WHEN geom IS NULL THEN 'incomplete' ELSE 'partial' END
                        WHEN geom IS NULL OR ST_IsEmpty(geom) THEN 'invalid'
                        WHEN NOT ST_IsValid(geom) THEN 'invalid'
                        ELSE 'assembled'
                    END AS assembly_status,
                    jsonb_build_object(
                        'member_count', member_count,
                        'path_members', path_members,
                        'present_path_geometries', present_path_geometries,
                        'missing_path_members', missing_path_members,
                        'null_path_geometries', null_path_geometries,
                        'stop_members', stop_members,
                        'platform_members', platform_members,
                        'unresolved_stop_members', unresolved_stop_members,
                        'unresolved_platform_members', unresolved_platform_members,
                        'nested_relation_members', nested_relation_members,
                        'assembler', 'PostGIS ST_UnaryUnion + ST_LineMerge',
                        'member_order', 'preserved in derived.osm_route_members',
                        'geometry_type', GeometryType(geom),
                        'is_valid', CASE WHEN geom IS NULL THEN NULL ELSE ST_IsValid(geom) END
                    ) AS diagnostics,
                    geom,
                    :run_id AS import_run_id
                FROM route_rows
            )
            INSERT INTO derived.osm_relation_geometries AS current
                (source_id, relation_id, relation_type, geometry_kind, assembly_method,
                 assembly_status, diagnostics, geom, import_run_id, assembled_at)
            SELECT source_id, relation_id, relation_type, geometry_kind, assembly_method,
                   assembly_status, diagnostics, geom, import_run_id, now()
            FROM prepared
            ON CONFLICT (source_id, relation_id) DO UPDATE SET
                relation_type = EXCLUDED.relation_type,
                geometry_kind = EXCLUDED.geometry_kind,
                assembly_method = EXCLUDED.assembly_method,
                assembly_status = EXCLUDED.assembly_status,
                diagnostics = EXCLUDED.diagnostics,
                geom = EXCLUDED.geom,
                import_run_id = EXCLUDED.import_run_id,
                assembled_at = EXCLUDED.assembled_at
            """
        ),
        parameters,
    )
    rows = connection.execute(
        text(
            """
            SELECT assembly_status, count(*) AS count
            FROM derived.osm_relation_geometries
            WHERE import_run_id = :run_id
            GROUP BY assembly_status
            """
        ),
        {"run_id": run_id},
    )
    return {str(row.assembly_status): int(row._mapping["count"]) for row in rows}


def import_region(
    region_name: str,
    *,
    engine: Engine | None = None,
    _defer_completion: bool = False,
) -> dict[str, int]:
    root = project_root()
    source_config = load_source(root)
    region: RegionConfig = load_region(region_name, root)
    authoritative = isinstance(region, RelationPolygonRegionConfig) and region.authoritative
    if authoritative and not _defer_completion:
        raise ValueError(
            f"Authoritative profile {region.name!r} must use the full refresh command"
        )
    database = engine or get_engine()
    with database.begin() as connection:
        source = _registered_source(connection, source_config)

    extract = root / "data/cache/osm" / str(source["version"]) / f"{region.name}.osm.pbf"
    run_id = start_import_run(
        database,
        source_id=int(source["id"]),
        source_version=str(source["version"]),
        checksum=str(source["checksum"]),
        profile=region.name,
        authoritative_snapshot=authoritative,
        details={"region": region.name, "extract": _relative_to_root(extract, root)},
    )
    started = datetime.now(UTC)
    try:
        if not extract.is_file():
            raise FileNotFoundError(f"Extract is missing: {extract}; run extract first")
        validate_pbf(extract)
        extract_checksum = sha256_file(extract)
        _cleanup_work_tables(database)
        connection_arguments, command_environment = _osm2pgsql_connection(database.url)
        run_command(
            [
                "osm2pgsql",
                "--create",
                "--slim",
                "--drop",
                "--output=flex",
                f"--style={root / 'config/osm/flex.lua'}",
                "--cache=512",
                *connection_arguments,
                str(extract),
            ],
            env=command_environment,
        )
        with database.begin() as connection:
            counts = _merge_work_tables(connection, int(source["id"]), run_id)
            _record_profile_memberships(
                connection, int(source["id"]), region.name, run_id
            )
            counts["area_geometry_candidates"] = _work_count(
                connection, "derived._osm_relation_geometries"
            )
            geometry_statuses = _merge_relation_geometries(connection, int(source["id"]), run_id)
            counts["relation_geometries"] = sum(geometry_statuses.values())
        duration = (datetime.now(UTC) - started).total_seconds()
        run_details = {
            "extract_checksum": extract_checksum,
            "staging_duration_seconds": duration,
            "counts": counts,
            "geometry_statuses": geometry_statuses,
        }
        if _defer_completion:
            stage_import_run(
                database,
                run_id,
                processed_count=counts["processed"],
                inserted_count=counts["inserted"],
                updated_count=counts["updated"],
                skipped_count=counts["skipped"],
                details=run_details,
            )
        else:
            finish_import_run(
                database,
                run_id,
                status="success",
                processed_count=counts["processed"],
                inserted_count=counts["inserted"],
                updated_count=counts["updated"],
                skipped_count=counts["skipped"],
                details=run_details,
            )
        result = {"run_id": run_id, **counts}
        print(json.dumps(result, indent=2))
        return result
    except BaseException as exc:
        finish_import_run(
            database,
            run_id,
            status="failed",
            error_count=1,
            details={"error_type": type(exc).__name__, "error": str(exc)[:2000]},
        )
        raise
    finally:
        try:
            _cleanup_work_tables(database)
        except Exception as cleanup_error:
            print(f"Warning: could not remove OSM work tables: {cleanup_error}")


def _finalize_authoritative_snapshot(
    connection: Connection,
    *,
    source_id: int,
    profile: str,
    run_id: int,
    authoritative_profiles: tuple[str, ...],
    details: dict[str, Any],
) -> dict[str, int]:
    run = connection.execute(
        text(
            """
            SELECT id FROM meta.import_runs
            WHERE id=:run_id AND source_id=:source_id AND profile=:profile
              AND authoritative_snapshot AND status='staged'
            FOR UPDATE
            """
        ),
        {"run_id": run_id, "source_id": source_id, "profile": profile},
    ).one_or_none()
    if run is None:
        raise RuntimeError("Lifecycle finalization requires the staged authoritative run")

    missing_memberships = int(
        connection.execute(
            text(
                """
                UPDATE meta.osm_profile_memberships
                SET lifecycle_status='missing', missing_since=COALESCE(missing_since, now()),
                    updated_at=now()
                WHERE source_id=:source_id AND profile=:profile
                  AND lifecycle_status='present' AND last_seen_import_run_id<>:run_id
                RETURNING 1
                """
            ),
            {"source_id": source_id, "profile": profile, "run_id": run_id},
        ).rowcount
        or 0
    )
    missing_bindings = int(
        connection.execute(
            text(
                """
                UPDATE catalog.object_sources AS binding
                SET source_status='missing', missing_since=COALESCE(missing_since, now()),
                    updated_at=now()
                WHERE binding.source_id=:source_id AND binding.source_status='present'
                  AND EXISTS (
                    SELECT 1 FROM meta.osm_profile_memberships AS missing
                    WHERE missing.source_id=binding.source_id
                      AND missing.profile=:profile
                      AND missing.source_object_type=binding.source_object_type
                      AND missing.source_object_id=binding.source_object_id::bigint
                      AND missing.lifecycle_status='missing'
                  )
                  AND NOT EXISTS (
                    SELECT 1 FROM meta.osm_profile_memberships AS present
                    WHERE present.source_id=binding.source_id
                      AND present.profile=ANY(:authoritative_profiles)
                      AND present.source_object_type=binding.source_object_type
                      AND present.source_object_id=binding.source_object_id::bigint
                      AND present.lifecycle_status='present'
                  )
                RETURNING 1
                """
            ),
            {
                "source_id": source_id,
                "profile": profile,
                "authoritative_profiles": list(authoritative_profiles),
            },
        ).rowcount
        or 0
    )
    connection.execute(
        text(
            """
            UPDATE catalog.object_category_sources AS category_source
            SET status='inactive', updated_at=now()
            FROM catalog.object_sources AS binding
            WHERE category_source.object_source_id=binding.id
              AND binding.source_id=:source_id AND binding.source_status='missing'
            """
        ),
        {"source_id": source_id},
    )
    connection.execute(
        text(
            """
            UPDATE catalog.object_categories AS category
            SET lifecycle_status=CASE WHEN EXISTS (
                  SELECT 1 FROM catalog.object_category_sources AS source
                  WHERE source.object_id=category.object_id
                    AND source.category_key=category.category_key AND source.status='active'
                ) THEN 'active' ELSE 'inactive' END,
                updated_at=now()
            WHERE EXISTS (
              SELECT 1 FROM catalog.object_category_sources AS source
              JOIN catalog.object_sources AS binding ON binding.id=source.object_source_id
              WHERE source.object_id=category.object_id
                AND source.category_key=category.category_key
                AND binding.source_id=:source_id AND binding.source_status='missing'
            )
            """
        ),
        {"source_id": source_id},
    )
    inactive_objects = int(
        connection.execute(
            text(
                """
                UPDATE catalog.objects AS object
                SET lifecycle_status=CASE WHEN EXISTS (
                      SELECT 1 FROM catalog.object_sources AS remaining
                      WHERE remaining.object_id=object.id AND remaining.source_status='present'
                    ) THEN 'active' ELSE 'inactive' END,
                    retired_at=NULL, updated_at=now()
                WHERE object.lifecycle_status IN ('active','inactive')
                  AND EXISTS (
                    SELECT 1 FROM catalog.object_sources AS binding
                    WHERE binding.object_id=object.id AND binding.source_id=:source_id
                      AND binding.source_status='missing'
                  )
                RETURNING 1
                """
            ),
            {"source_id": source_id},
        ).rowcount
        or 0
    )
    lifecycle = {
        "missing_memberships": missing_memberships,
        "missing_bindings": missing_bindings,
        "affected_objects": inactive_objects,
    }
    final_details = {
        **details,
        "lifecycle": lifecycle,
    }
    result = connection.execute(
        text(
            """
            UPDATE meta.import_runs
            SET status='success', finished_at=now(), lifecycle_finalized_at=now(),
                details=details || CAST(:details AS jsonb), updated_at=now()
            WHERE id=:run_id AND status='staged'
            """
        ),
        {"run_id": run_id, "details": json.dumps(final_details, default=str)},
    )
    if result.rowcount != 1:
        raise RuntimeError(f"Could not complete authoritative import run {run_id}")
    return lifecycle


def refresh_region(region_name: str, *, engine: Engine | None = None) -> dict[str, Any]:
    """Run the complete production-capable staging/canonical/category snapshot."""
    from app.data.categories import run_osm_category_pipeline

    root = project_root()
    region = load_region(region_name, root)
    if not isinstance(region, RelationPolygonRegionConfig) or not region.authoritative:
        raise ValueError(
            "Full refresh is only available for authoritative relation_polygon profiles"
        )
    database = engine or get_engine()
    staging = import_region(region_name, engine=database, _defer_completion=True)
    run_id = int(staging["run_id"])
    started = datetime.now(UTC)
    try:
        with database.connect() as connection:
            source_id = int(
                connection.scalar(
                    text("SELECT source_id FROM meta.import_runs WHERE id=:run_id"),
                    {"run_id": run_id},
                )
            )
        # The first full-city snapshot can add more than a million membership rows.
        # Give candidate discovery current cardinality statistics instead of relying
        # on asynchronous auto-analyze to arrive after its plan has been chosen.
        with database.begin() as connection:
            connection.execute(text("ANALYZE meta.osm_profile_memberships"))
        category = run_osm_category_pipeline(
            source_id,
            run_id,
            profile=region.name,
            engine=database,
        )
        category_duration = (datetime.now(UTC) - started).total_seconds()
        authoritative_profiles = tuple(
            name
            for name, configured in load_regions(root).items()
            if isinstance(configured, RelationPolygonRegionConfig) and configured.authoritative
        )
        with database.begin() as connection:
            lifecycle = _finalize_authoritative_snapshot(
                connection,
                source_id=source_id,
                profile=region.name,
                run_id=run_id,
                authoritative_profiles=authoritative_profiles,
                details={
                    "category_duration_seconds": category_duration,
                    "category": asdict(category),
                },
            )
            for table in (
                "staging.osm_nodes",
                "staging.osm_ways",
                "staging.osm_relations",
                "derived.osm_relation_geometries",
                "catalog.object_sources",
                "catalog.objects",
                "catalog.object_categories",
            ):
                connection.execute(text(f"ANALYZE {table}"))
        result: dict[str, Any] = {
            "run_id": run_id,
            "staging": staging,
            "category": asdict(category),
            "lifecycle": lifecycle,
        }
        print(json.dumps(result, indent=2, default=str))
        return result
    except BaseException as exc:
        finish_import_run(
            database,
            run_id,
            status="failed",
            error_count=1,
            details={
                "failed_stage": "canonical_category_or_finalization",
                "error_type": type(exc).__name__,
                "error": str(exc)[:2000],
            },
        )
        raise


def status(engine: Engine | None = None) -> list[dict[str, Any]]:
    database = engine or get_engine()
    source = load_source()
    with database.begin() as connection:
        ensure_source(connection, source)
        rows = (
            connection.execute(
                text(
                    """
                SELECT s.id, s.name, s.provider, s.version, s.checksum, s.local_filename,
                       s.source_updated_at, s.downloaded_at,
                       (SELECT count(*) FROM staging.osm_nodes n WHERE n.source_id = s.id) nodes,
                       (SELECT count(*) FROM staging.osm_ways w WHERE w.source_id = s.id) ways,
                       (SELECT count(*) FROM staging.osm_relations r
                        WHERE r.source_id = s.id) relations,
                       (SELECT count(*) FROM staging.osm_relation_members m
                        WHERE m.source_id = s.id) relation_members,
                       (SELECT count(*) FROM derived.osm_relation_geometries g
                        WHERE g.source_id = s.id) relation_geometries
                FROM meta.dataset_sources s
                WHERE s.name = :name
                """
                ),
                {"name": source.name},
            )
            .mappings()
            .all()
        )
    result = [dict(row) for row in rows]
    print(json.dumps(result, default=str, indent=2))
    return result


def inspect(engine: Engine | None = None) -> dict[str, Any]:
    database = engine or get_engine()
    queries = {
        "objects_by_type": """
            SELECT osm_type, count(*) count FROM (
              SELECT osm_type FROM staging.osm_nodes
              UNION ALL SELECT osm_type FROM staging.osm_ways
              UNION ALL SELECT osm_type FROM staging.osm_relations
            ) objects GROUP BY osm_type ORDER BY osm_type
        """,
        "geometries": """
            SELECT ST_GeometryType(geom) geometry_type, count(*) count FROM (
              SELECT geom FROM staging.osm_nodes WHERE geom IS NOT NULL
              UNION ALL SELECT geom FROM staging.osm_ways WHERE geom IS NOT NULL
              UNION ALL SELECT geom FROM staging.osm_relations WHERE geom IS NOT NULL
            ) geometries GROUP BY ST_GeometryType(geom) ORDER BY geometry_type
        """,
        "recent_runs": """
            SELECT id, status, source_version, processed_count, inserted_count,
                   updated_count, error_count, started_at, finished_at
            FROM meta.import_runs ORDER BY id DESC LIMIT 5
        """,
        "raw_tag_samples": """
            SELECT osm_type, osm_id, tags FROM (
              SELECT osm_type, osm_id, tags FROM staging.osm_nodes
              UNION ALL SELECT osm_type, osm_id, tags FROM staging.osm_ways
            ) tagged WHERE tags ?| ARRAY['amenity', 'leisure', 'highway'] LIMIT 10
        """,
        "relation_members": """
            SELECT relation_id, sequence, member_type, member_id, role
            FROM staging.osm_relation_members ORDER BY relation_id, sequence LIMIT 10
        """,
        "relation_geometries": """
            SELECT relation_type, assembly_status, count(*) count
            FROM derived.osm_relation_geometries
            GROUP BY relation_type, assembly_status
            ORDER BY relation_type, assembly_status
        """,
        "route_member_kinds": """
            SELECT member_kind, count(*) count
            FROM derived.osm_route_members
            GROUP BY member_kind ORDER BY member_kind
        """,
    }
    result: dict[str, Any] = {}
    with database.connect() as connection:
        for name, query in queries.items():
            result[name] = [dict(row) for row in connection.execute(text(query)).mappings()]
    print(json.dumps(result, default=str, indent=2, ensure_ascii=False))
    return result
