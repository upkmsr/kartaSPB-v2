import argparse
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from time import monotonic
from typing import Any

from sqlalchemy import Connection, Engine, text

from app.db.session import get_engine

GRID_VERSION = "spb-square-200m-v1"
CELL_SIZE_M = 200
METRIC_SRID = 32636
DISPLAY_SRID = 4326
EXPECTED_DISTRICT_COUNT = 18
GRID_VERSION_PATTERN = re.compile(r"^spb-square-(?P<cell_size_m>[1-9][0-9]*)m-v[1-9][0-9]*$")


class GridBootstrapError(RuntimeError):
    """Raised when the source boundary or an existing grid violates the F6 contract."""


@dataclass(frozen=True)
class GridBootstrapReport:
    grid_version: str
    cell_size_m: int
    metric_srid: int
    display_srid: int
    cell_count: int
    district_count: int
    district_cell_counts: dict[str, int]
    invalid_geometry_count: int
    missing_district_count: int
    duplicate_coordinate_count: int
    bbox: list[float]
    checksum_sha256: str
    created_count: int
    unchanged_count: int
    duration_seconds: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_DISTRICT_VALIDATION_SQL = text(
    """
    SELECT
        count(*) FILTER (WHERE d.enabled) AS enabled_count,
        count(*) FILTER (
            WHERE d.enabled AND (
                o.id IS NULL
                OR o.lifecycle_status <> 'active'
                OR o.geom IS NULL
                OR ST_IsEmpty(o.geom)
                OR NOT ST_IsValid(o.geom)
                OR ST_SRID(o.geom) <> :display_srid
            )
        ) AS invalid_count
    FROM domain.districts AS d
    LEFT JOIN catalog.objects AS o ON o.id = d.canonical_object_id
    """
)

_CREATE_EXPECTED_SQL = text(
    """
    CREATE TEMPORARY TABLE f6_expected_analysis_cells ON COMMIT DROP AS
    WITH district_geometries AS MATERIALIZED (
        SELECT
            d.id AS district_id,
            d.display_order,
            ST_Transform(o.geom, :metric_srid) AS geom_metric
        FROM domain.districts AS d
        JOIN catalog.objects AS o ON o.id = d.canonical_object_id
        WHERE d.enabled
          AND o.lifecycle_status = 'active'
          AND o.geom IS NOT NULL
          AND NOT ST_IsEmpty(o.geom)
          AND ST_IsValid(o.geom)
          AND ST_SRID(o.geom) = :display_srid
    ),
    city AS MATERIALIZED (
        SELECT ST_UnaryUnion(ST_Collect(geom_metric)) AS geom_metric
        FROM district_geometries
    ),
    squares AS MATERIALIZED (
        SELECT
            square.i::integer AS grid_i,
            square.j::integer AS grid_j,
            square.geom::geometry(Polygon, 32636) AS geom_metric,
            ST_Centroid(square.geom)::geometry(Point, 32636) AS center_metric
        FROM city
        CROSS JOIN LATERAL ST_SquareGrid(
            :cell_size_m,
            ST_Envelope(city.geom_metric)
        ) AS square
    )
    SELECT
        :grid_version || ':' || squares.grid_i || ':' || squares.grid_j AS cell_id,
        CAST(:grid_version AS text) AS grid_version,
        squares.grid_i,
        squares.grid_j,
        CAST(:cell_size_m AS integer) AS cell_size_m,
        assigned.district_id,
        ST_Transform(squares.center_metric, :display_srid)::geometry(Point, 4326) AS center,
        squares.center_metric,
        ST_Transform(squares.geom_metric, :display_srid)::geometry(Polygon, 4326) AS geom,
        squares.geom_metric
    FROM squares
    CROSS JOIN LATERAL (
        SELECT district_geometries.district_id
        FROM district_geometries
        WHERE ST_Covers(district_geometries.geom_metric, squares.center_metric)
        ORDER BY district_geometries.display_order, district_geometries.district_id
        LIMIT 1
    ) AS assigned
    WHERE ST_Covers((SELECT geom_metric FROM city), squares.center_metric)
    """
)

_EXPECTED_VALIDATION_SQL = text(
    """
    SELECT
        count(*) AS cell_count,
        count(DISTINCT district_id) AS district_count,
        count(*) FILTER (
            WHERE ST_GeometryType(geom) <> 'ST_Polygon'
               OR ST_GeometryType(geom_metric) <> 'ST_Polygon'
               OR ST_SRID(geom) <> :display_srid
               OR ST_SRID(center) <> :display_srid
               OR ST_SRID(geom_metric) <> :metric_srid
               OR ST_SRID(center_metric) <> :metric_srid
               OR ST_IsEmpty(geom)
               OR NOT ST_IsValid(geom)
               OR abs(
                   ST_Area(geom_metric)
                   - (CAST(:cell_size_m AS double precision) * :cell_size_m)
               ) > 0.01
               OR NOT ST_Covers(geom_metric, center_metric)
        ) AS invalid_geometry_count,
        :expected_district_count - count(DISTINCT district_id) AS missing_district_count,
        count(*) - count(DISTINCT (grid_i, grid_j)) AS duplicate_coordinate_count,
        ST_XMin(ST_Extent(geom)::box3d) AS min_lon,
        ST_YMin(ST_Extent(geom)::box3d) AS min_lat,
        ST_XMax(ST_Extent(geom)::box3d) AS max_lon,
        ST_YMax(ST_Extent(geom)::box3d) AS max_lat
    FROM f6_expected_analysis_cells
    """
)

_MISMATCH_SQL = text(
    """
    SELECT count(*)
    FROM f6_expected_analysis_cells AS expected
    FULL JOIN (
        SELECT *
        FROM analytics.analysis_cells
        WHERE grid_version = :grid_version
    ) AS actual ON actual.cell_id = expected.cell_id
    WHERE expected.cell_id IS NULL
       OR actual.cell_id IS NULL
       OR actual.grid_i <> expected.grid_i
       OR actual.grid_j <> expected.grid_j
       OR actual.cell_size_m <> expected.cell_size_m
       OR actual.district_id <> expected.district_id
       OR NOT ST_Equals(actual.center, expected.center)
       OR NOT ST_Equals(actual.center_metric, expected.center_metric)
       OR NOT ST_Equals(actual.geom, expected.geom)
       OR NOT ST_Equals(actual.geom_metric, expected.geom_metric)
    """
)


def grid_version_for(cell_size_m: int, version: int = 1) -> str:
    if cell_size_m <= 0:
        raise GridBootstrapError("cell_size_m must be positive")
    if version <= 0:
        raise GridBootstrapError("grid version revision must be positive")
    return f"spb-square-{cell_size_m}m-v{version}"


def _validate_grid_spec(grid_version: str, cell_size_m: int) -> None:
    match = GRID_VERSION_PATTERN.fullmatch(grid_version)
    if match is None:
        raise GridBootstrapError(
            "grid_version must use the versioned spb-square-<cell-size>m-v<revision> format"
        )
    encoded_cell_size = int(match.group("cell_size_m"))
    if encoded_cell_size != cell_size_m:
        raise GridBootstrapError(
            "grid_version cell size does not match cell_size_m: "
            f"{encoded_cell_size} != {cell_size_m}"
        )


def _parameters(grid_version: str, cell_size_m: int) -> dict[str, int | str]:
    _validate_grid_spec(grid_version, cell_size_m)
    return {
        "grid_version": grid_version,
        "cell_size_m": cell_size_m,
        "metric_srid": METRIC_SRID,
        "display_srid": DISPLAY_SRID,
        "expected_district_count": EXPECTED_DISTRICT_COUNT,
    }


def _validate_district_source(
    connection: Connection, parameters: dict[str, int | str]
) -> None:
    row = connection.execute(_DISTRICT_VALIDATION_SQL, parameters).one()
    if row.enabled_count != EXPECTED_DISTRICT_COUNT:
        raise GridBootstrapError(
            f"expected {EXPECTED_DISTRICT_COUNT} enabled districts, found {row.enabled_count}"
        )
    if row.invalid_count:
        raise GridBootstrapError(
            f"district source contains {row.invalid_count} missing or invalid geometries"
        )


def _checksum(connection: Connection) -> str:
    digest = hashlib.sha256()
    rows = connection.execution_options(stream_results=True).execute(
        text(
            """
            SELECT
                cell_id,
                district_id::text,
                encode(ST_AsEWKB(geom_metric), 'hex') AS metric_wkb
            FROM f6_expected_analysis_cells
            ORDER BY cell_id
            """
        )
    )
    for cell_id, district_id, metric_wkb in rows:
        digest.update(f"{cell_id}\t{district_id}\t{metric_wkb}\n".encode())
    return digest.hexdigest()


def bootstrap_grid(
    engine: Engine | None = None,
    *,
    grid_version: str = GRID_VERSION,
    cell_size_m: int = CELL_SIZE_M,
) -> GridBootstrapReport:
    started = monotonic()
    target_engine = engine or get_engine()
    parameters = _parameters(grid_version, cell_size_m)
    with target_engine.begin() as connection:
        connection.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:grid_version))"), parameters
        )
        _validate_district_source(connection, parameters)
        connection.execute(_CREATE_EXPECTED_SQL, parameters)
        validation = connection.execute(_EXPECTED_VALIDATION_SQL, parameters).one()

        if validation.cell_count == 0:
            raise GridBootstrapError("generated grid is empty")
        if validation.district_count != EXPECTED_DISTRICT_COUNT:
            raise GridBootstrapError(
                "generated grid does not cover all enabled districts: "
                f"{validation.district_count}/{EXPECTED_DISTRICT_COUNT}"
            )
        if validation.invalid_geometry_count or validation.duplicate_coordinate_count:
            raise GridBootstrapError(
                "generated grid failed geometry or coordinate uniqueness validation"
            )

        existing_count = connection.scalar(
            text(
                "SELECT count(*) FROM analytics.analysis_cells "
                "WHERE grid_version = :grid_version"
            ),
            parameters,
        )
        if existing_count is None:
            existing_count = 0
        created_count = 0
        unchanged_count = 0
        if existing_count:
            mismatch_count = connection.scalar(_MISMATCH_SQL, parameters)
            if mismatch_count:
                raise GridBootstrapError(
                    "existing grid differs from deterministic output; refusing automatic repair"
                )
            unchanged_count = validation.cell_count
        else:
            result = connection.execute(
                text(
                    """
                    INSERT INTO analytics.analysis_cells (
                        cell_id, grid_version, grid_i, grid_j, cell_size_m, district_id,
                        center, center_metric, geom, geom_metric
                    )
                    SELECT
                        cell_id, grid_version, grid_i, grid_j, cell_size_m, district_id,
                        center, center_metric, geom, geom_metric
                    FROM f6_expected_analysis_cells
                    ORDER BY cell_id
                    """
                )
            )
            created_count = result.rowcount

        district_rows = connection.execute(
            text(
                """
                SELECT district_id::text, count(*)
                FROM f6_expected_analysis_cells
                GROUP BY district_id
                ORDER BY district_id
                """
            )
        )
        district_cell_counts: dict[str, int] = {
            str(district_id): int(str(count)) for district_id, count in district_rows
        }
        checksum = _checksum(connection)

    return GridBootstrapReport(
        grid_version=grid_version,
        cell_size_m=cell_size_m,
        metric_srid=METRIC_SRID,
        display_srid=DISPLAY_SRID,
        cell_count=validation.cell_count,
        district_count=validation.district_count,
        district_cell_counts=district_cell_counts,
        invalid_geometry_count=validation.invalid_geometry_count,
        missing_district_count=validation.missing_district_count,
        duplicate_coordinate_count=validation.duplicate_coordinate_count,
        bbox=[
            validation.min_lon,
            validation.min_lat,
            validation.max_lon,
            validation.max_lat,
        ],
        checksum_sha256=checksum,
        created_count=created_count,
        unchanged_count=unchanged_count,
        duration_seconds=round(monotonic() - started, 3),
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Build the deterministic F6 analysis grid")
    commands = parser.add_subparsers(dest="command", required=True)
    bootstrap = commands.add_parser(
        "bootstrap", help="Create or verify a deterministic versioned square grid"
    )
    bootstrap.add_argument("--grid-version", default=GRID_VERSION)
    bootstrap.add_argument("--cell-size-m", type=int, default=CELL_SIZE_M)
    args = parser.parse_args(argv)
    if args.command == "bootstrap":
        print(
            json.dumps(
                bootstrap_grid(
                    grid_version=args.grid_version,
                    cell_size_m=args.cell_size_m,
                ).to_dict(),
                ensure_ascii=False,
                sort_keys=True,
            )
        )


if __name__ == "__main__":
    main()
