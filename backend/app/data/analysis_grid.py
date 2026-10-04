from dataclasses import dataclass
from typing import Any

from sqlalchemy import Engine, text

from app.analytics.grid import CELL_SIZE_M, DISPLAY_SRID, GRID_VERSION, METRIC_SRID


@dataclass(frozen=True)
class AnalysisGridMetadata:
    grid_version: str
    cell_size_m: int
    metric_srid: int
    display_srid: int
    cell_count: int
    district_count: int
    district_cell_counts: list[dict[str, Any]]
    bbox: list[float] | None


class AnalysisGridService:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def metadata(self) -> AnalysisGridMetadata:
        with self.engine.connect() as connection:
            summary = connection.execute(
                text(
                    """
                    SELECT
                        count(*) AS cell_count,
                        count(DISTINCT district_id) AS district_count,
                        ST_XMin(ST_Extent(geom)::box3d) AS min_lon,
                        ST_YMin(ST_Extent(geom)::box3d) AS min_lat,
                        ST_XMax(ST_Extent(geom)::box3d) AS max_lon,
                        ST_YMax(ST_Extent(geom)::box3d) AS max_lat
                    FROM analytics.analysis_cells
                    WHERE grid_version = :grid_version
                    """
                ),
                {"grid_version": GRID_VERSION},
            ).one()
            counts = connection.execute(
                text(
                    """
                    SELECT district_id, count(*) AS cell_count
                    FROM analytics.analysis_cells
                    WHERE grid_version = :grid_version
                    GROUP BY district_id
                    ORDER BY district_id
                    """
                ),
                {"grid_version": GRID_VERSION},
            )
            district_cell_counts = [
                {"district_id": row.district_id, "cell_count": row.cell_count}
                for row in counts
            ]
        bbox = (
            None
            if summary.cell_count == 0
            else [summary.min_lon, summary.min_lat, summary.max_lon, summary.max_lat]
        )
        return AnalysisGridMetadata(
            grid_version=GRID_VERSION,
            cell_size_m=CELL_SIZE_M,
            metric_srid=METRIC_SRID,
            display_srid=DISPLAY_SRID,
            cell_count=summary.cell_count,
            district_count=summary.district_count,
            district_cell_counts=district_cell_counts,
            bbox=bbox,
        )

    def tile(self, z: int, x: int, y: int) -> bytes:
        with self.engine.connect() as connection:
            payload = connection.scalar(
                text(
                    """
                    WITH tile AS (
                        SELECT ST_TileEnvelope(:z, :x, :y) AS bounds
                    ),
                    tile_rows AS (
                        SELECT
                            cell.cell_id,
                            cell.district_id::text AS district_id,
                            cell.grid_version,
                            ST_AsMVTGeom(
                                ST_Transform(cell.geom, 3857),
                                tile.bounds,
                                4096,
                                64,
                                true
                            ) AS geom
                        FROM analytics.analysis_cells AS cell
                        CROSS JOIN tile
                        WHERE cell.grid_version = :grid_version
                          AND cell.geom && ST_Transform(tile.bounds, 4326)
                          AND ST_Intersects(ST_Transform(cell.geom, 3857), tile.bounds)
                    )
                    SELECT ST_AsMVT(tile_rows, 'analysis_grid', 4096, 'geom')
                    FROM tile_rows
                    """
                ),
                {"z": z, "x": x, "y": y, "grid_version": GRID_VERSION},
            )
        if payload is None:
            return b""
        return bytes(payload)
