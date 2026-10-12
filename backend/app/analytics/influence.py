import hashlib
from dataclasses import dataclass
from typing import Any

from sqlalchemy import Engine, TextClause, text

from app.analytics.heatmap import HeatmapError, HeatmapService, encode_heatmap_spec
from app.analytics.scoring.engine import ScoringError, ScoringPlan, ScoringService

INFLUENCE_DELIVERY_VERSION = "influence-mvt-v1"
INFLUENCE_SOURCE_LAYER = "analysis_influence"
MAX_INFLUENCE_METRICS = 8


class InfluenceError(ValueError):
    """Raised when an independent influence request is invalid."""


@dataclass(frozen=True)
class InfluenceChannel:
    metric_key: str
    score_run_id: str
    property_name: str

    def to_dict(self) -> dict[str, str]:
        return {
            "metric_key": self.metric_key,
            "score_run_id": self.score_run_id,
            "property_name": self.property_name,
        }


@dataclass(frozen=True)
class PreparedInfluence:
    grid_version: str
    influence_signature: str
    spec: str
    cell_count: int
    channels: tuple[InfluenceChannel, ...]
    tile_url_template: str
    delivery_version: str = INFLUENCE_DELIVERY_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "grid_version": self.grid_version,
            "influence_signature": self.influence_signature,
            "spec": self.spec,
            "cell_count": self.cell_count,
            "channels": [channel.to_dict() for channel in self.channels],
            "tile_url_template": self.tile_url_template,
            "delivery_version": self.delivery_version,
        }


@dataclass(frozen=True)
class InfluenceTile:
    payload: bytes
    etag: str
    influence_signature: str


def influence_signature(spec: str) -> str:
    return hashlib.sha256(f"influence-spec-v1:{spec}".encode()).hexdigest()


class InfluenceService:
    def __init__(
        self,
        engine: Engine,
        scoring: ScoringService,
        allowed_metric_keys: set[str],
    ) -> None:
        self._engine = engine
        self._scoring = scoring
        self._heatmap = HeatmapService(engine, scoring)
        self._allowed_metric_keys = allowed_metric_keys

    def prepare(self, grid_version: str, metric_keys: list[str]) -> PreparedInfluence:
        canonical_keys = sorted(set(metric_keys))
        if not 1 <= len(canonical_keys) <= MAX_INFLUENCE_METRICS:
            raise InfluenceError("influence request must contain between 1 and 8 metrics")
        if len(canonical_keys) != len(metric_keys):
            raise InfluenceError("influence metric keys must be unique")
        if any(key not in self._allowed_metric_keys for key in canonical_keys):
            raise InfluenceError("unknown or unsupported influence metric")
        try:
            plan = self._scoring.resolve_current_plan(
                grid_version,
                {key: 1.0 for key in canonical_keys},
            )
        except ScoringError as exc:
            raise InfluenceError(str(exc)) from exc
        return self._prepared(plan)

    def plan_from_spec(self, encoded_spec: str) -> ScoringPlan:
        try:
            plan = self._heatmap.plan_from_spec(encoded_spec)
        except HeatmapError as exc:
            raise InfluenceError(str(exc)) from exc
        if len(plan.metrics) > MAX_INFLUENCE_METRICS:
            raise InfluenceError("influence spec contains too many metrics")
        if any(metric.metric_key not in self._allowed_metric_keys for metric in plan.metrics):
            raise InfluenceError("influence spec contains an unsupported metric")
        if any(metric.weight != 1.0 for metric in plan.metrics):
            raise InfluenceError("influence spec weights must be canonical")
        return plan

    def tile(
        self,
        requested_signature: str,
        z: int,
        x: int,
        y: int,
        encoded_spec: str,
    ) -> InfluenceTile:
        plan = self.plan_from_spec(encoded_spec)
        expected_signature = influence_signature(encoded_spec)
        if requested_signature != expected_signature:
            raise InfluenceError("influence signature does not match spec")
        statement, params = self.tile_statement(plan, z, x, y)
        with self._engine.connect() as connection:
            payload = connection.scalar(statement, params)
        etag = hashlib.sha256(
            f"{INFLUENCE_DELIVERY_VERSION}:{expected_signature}:{z}:{x}:{y}".encode()
        ).hexdigest()
        return InfluenceTile(
            payload=b"" if payload is None else bytes(payload),
            etag=etag,
            influence_signature=expected_signature,
        )

    @staticmethod
    def tile_statement(
        plan: ScoringPlan, z: int, x: int, y: int
    ) -> tuple[TextClause, dict[str, object]]:
        params: dict[str, object] = {
            "z": z,
            "x": x,
            "y": y,
            "grid_version": plan.grid_version,
        }
        overview = z <= 10
        if overview:
            params["aggregation_factor"] = {8: 8, 9: 4, 10: 2}.get(z, 8)
        score_columns: list[str] = []
        output_columns: list[str] = []
        run_parameters: list[str] = []
        for index, metric in enumerate(plan.metrics):
            parameter = f"run_{index}"
            params[parameter] = str(metric.score_run_id)
            run_parameters.append(f"CAST(:{parameter} AS uuid)")
            score_columns.append(
                "max(score.score) FILTER (WHERE score.score_run_id = "
                f"CAST(:{parameter} AS uuid))::double precision AS score_{index}"
            )
            output_columns.append(f"score_{index}")
        base_sql = (
            "WITH tile AS ("
            "SELECT ST_TileEnvelope(:z, :x, :y) AS bounds"
            "), tile_cells AS MATERIALIZED ("
            "SELECT cell.cell_id, cell.district_id, cell.grid_i, cell.grid_j, "
            "cell.geom, tile.bounds "
            "FROM analytics.analysis_cells AS cell CROSS JOIN tile "
            "WHERE cell.grid_version = :grid_version "
            "AND cell.geom && ST_Transform(tile.bounds, 4326) "
            "AND ST_Intersects(ST_Transform(cell.geom, 3857), tile.bounds)"
            "), scored AS ("
            "SELECT cell.cell_id, cell.district_id, cell.grid_i, cell.grid_j, "
            "cell.geom, cell.bounds, "
            + ",".join(score_columns)
            + " FROM tile_cells AS cell "
            "JOIN analytics.cell_metric_scores AS score ON score.cell_id = cell.cell_id "
            "WHERE score.score_run_id IN ("
            + ",".join(run_parameters)
            + ") GROUP BY cell.cell_id, cell.district_id, cell.grid_i, cell.grid_j, "
            "cell.geom, cell.bounds"
            ")"
        )
        if overview:
            score_averages = ",".join(
                f"avg(score_{index}) AS score_{index}"
                for index in range(len(plan.metrics))
            )
            base_sql += (
                ", aggregated AS MATERIALIZED (SELECT "
                ":grid_version || ':overview:' || "
                "floor(grid_i / CAST(:aggregation_factor AS double precision))::integer || ':' || "
                "floor(grid_j / CAST(:aggregation_factor AS double precision))::integer || ':' || "
                "district_id::text AS cell_id, district_id, "
                + score_averages
                + ", ST_Collect(geom) AS geom, "
                "ST_TileEnvelope(:z, :x, :y)::box2d AS bounds "
                "FROM scored GROUP BY district_id, "
                "floor(grid_i / CAST(:aggregation_factor AS double precision)), "
                "floor(grid_j / CAST(:aggregation_factor AS double precision)))"
            )
        source_cte = "aggregated" if overview else "scored"
        statement = text(
            base_sql
            + ", tile_rows AS MATERIALIZED ("
            "SELECT cell_id, district_id::text AS district_id, "
            + ",".join(output_columns)
            + ", ST_AsMVTGeom(ST_Transform(geom, 3857), bounds, 4096, 64, true) "
            "AS mvt_geom FROM "
            + source_cte
            + " ORDER BY cell_id"
            + ") SELECT ST_AsMVT(tile_rows, 'analysis_influence', 4096, 'mvt_geom') "
            "FROM tile_rows"
        )
        return statement, params

    @staticmethod
    def _prepared(plan: ScoringPlan) -> PreparedInfluence:
        spec = encode_heatmap_spec(plan)
        signature = influence_signature(spec)
        channels = tuple(
            InfluenceChannel(
                metric_key=metric.metric_key,
                score_run_id=str(metric.score_run_id),
                property_name=f"score_{index}",
            )
            for index, metric in enumerate(plan.metrics)
        )
        return PreparedInfluence(
            grid_version=plan.grid_version,
            influence_signature=signature,
            spec=spec,
            cell_count=plan.cell_count,
            channels=channels,
            tile_url_template=(
                f"/api/analysis/influence/tiles/{signature}/"
                f"{{z}}/{{x}}/{{y}}.mvt?spec={spec}"
            ),
        )
