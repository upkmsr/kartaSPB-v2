import json
import os
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, cast
from urllib.request import Request, urlopen

from sqlalchemy import URL, Connection, Engine, text

from app.data.osm.config import RegionConfig, SourceConfig, load_region, load_source, project_root
from app.data.osm.database import (
    ensure_source,
    finish_import_run,
    record_download,
    start_import_run,
)
from app.data.osm.files import download_atomic, file_matches_sha256, sha256_file
from app.db.session import get_engine

WORK_TABLES = (
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


def validate_pbf(path: Path) -> None:
    run_command(["osmium", "fileinfo", "--input-format", "pbf", "--extended", str(path)])


def remote_metadata(url: str) -> RemoteMetadata:
    request = Request(url, method="HEAD", headers={"User-Agent": "KARTASPB-v2/1.0"})
    with urlopen(request, timeout=30) as response:
        last_modified = response.headers.get("Last-Modified")
        updated_at = parsedate_to_datetime(last_modified) if last_modified else None
        if updated_at and updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=UTC)
        version = (
            updated_at.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ") if updated_at else None
        )
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
    version = metadata.version or previous_version or datetime.now(UTC).strftime(
        "%Y%m%dT%H%M%SZ"
    )

    if not force and previous_version == version and previous_filename and previous_checksum:
        existing = root / previous_filename
        if file_matches_sha256(existing, previous_checksum):
            print(f"Source already current: {existing} ({previous_checksum})")
            return existing

    destination = (
        root
        / "data/sources/osm"
        / f"northwestern-fed-district-{version}.osm.pbf"
    )
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


def extract_region(
    region_name: str, *, force: bool = False, engine: Engine | None = None
) -> Path:
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

    version = str(source["version"])
    output = root / "data/cache/osm" / version / f"{region.name}.osm.pbf"
    checksum_file = output.with_suffix(f"{output.suffix}.sha256")
    if not force and output.is_file() and checksum_file.is_file():
        recorded = checksum_file.read_text(encoding="ascii").strip()
        if recorded and sha256_file(output) == recorded:
            print(f"Extract already current: {output} ({recorded})")
            return output

    output.parent.mkdir(parents=True, exist_ok=True)
    partial = output.with_name(f"{output.name}.part")
    partial.unlink(missing_ok=True)
    bbox = ",".join(str(value) for value in region.bbox)
    try:
        run_command(
            [
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
        )
        validate_pbf(partial)
        checksum = sha256_file(partial)
        partial.replace(output)
        checksum_file.write_text(f"{checksum}\n", encoding="ascii")
    except BaseException:
        partial.unlink(missing_ok=True)
        raise
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
    geometry_difference = (
        "OR target.geom IS DISTINCT FROM work.geom" if include_geometry else ""
    )
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
        text(
            "DELETE FROM staging.osm_nodes "
            "WHERE source_id = :source_id AND tags = '{}'::jsonb"
        ),
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
            "OR current.geom IS DISTINCT FROM EXCLUDED.geom"
            if object_type != "relation"
            else ""
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
    counts["relation_members"] = _work_count(
        connection, "staging._osm_relation_members"
    )
    counts["processed"] = counts["nodes"] + counts["ways"] + counts["relations"]
    counts["inserted"] = inserted
    counts["updated"] = updated
    counts["skipped"] = counts["processed"] - inserted - updated
    return counts


def import_region(region_name: str, *, engine: Engine | None = None) -> dict[str, int]:
    root = project_root()
    source_config = load_source(root)
    region: RegionConfig = load_region(region_name, root)
    database = engine or get_engine()
    with database.begin() as connection:
        source = _registered_source(connection, source_config)

    extract = root / "data/cache/osm" / str(source["version"]) / f"{region.name}.osm.pbf"
    run_id = start_import_run(
        database,
        source_id=int(source["id"]),
        source_version=str(source["version"]),
        checksum=str(source["checksum"]),
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
        duration = (datetime.now(UTC) - started).total_seconds()
        finish_import_run(
            database,
            run_id,
            status="success",
            processed_count=counts["processed"],
            inserted_count=counts["inserted"],
            updated_count=counts["updated"],
            skipped_count=counts["skipped"],
            details={
                "extract_checksum": extract_checksum,
                "duration_seconds": duration,
                "counts": counts,
            },
        )
        print(json.dumps({"run_id": run_id, **counts}, indent=2))
        return counts
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


def status(engine: Engine | None = None) -> list[dict[str, Any]]:
    database = engine or get_engine()
    source = load_source()
    with database.begin() as connection:
        ensure_source(connection, source)
        rows = connection.execute(
            text(
                """
                SELECT s.id, s.name, s.provider, s.version, s.checksum, s.local_filename,
                       s.source_updated_at, s.downloaded_at,
                       (SELECT count(*) FROM staging.osm_nodes n WHERE n.source_id = s.id) nodes,
                       (SELECT count(*) FROM staging.osm_ways w WHERE w.source_id = s.id) ways,
                       (SELECT count(*) FROM staging.osm_relations r
                        WHERE r.source_id = s.id) relations,
                       (SELECT count(*) FROM staging.osm_relation_members m
                        WHERE m.source_id = s.id) relation_members
                FROM meta.dataset_sources s
                WHERE s.name = :name
                """
            ),
            {"name": source.name},
        ).mappings().all()
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
    }
    result: dict[str, Any] = {}
    with database.connect() as connection:
        for name, query in queries.items():
            result[name] = [dict(row) for row in connection.execute(text(query)).mappings()]
    print(json.dumps(result, default=str, indent=2, ensure_ascii=False))
    return result
