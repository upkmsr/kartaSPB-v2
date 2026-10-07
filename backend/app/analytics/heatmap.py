import base64
import binascii
import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import Engine, TextClause, text

from app.analytics.scoring.engine import ScoringError, ScoringPlan, ScoringService

HEATMAP_SPEC_VERSION = "heatmap-spec-v1"
HEATMAP_DELIVERY_VERSION = "heatmap-mvt-v1"
HEATMAP_SOURCE_LAYER = "analysis_heatmap"
MAX_HEATMAP_METRICS = 12
MAX_DECODED_SPEC_BYTES = 4096


class HeatmapError(ValueError):
    """Raised when a heatmap request is invalid or cannot be reproduced."""


@dataclass(frozen=True)
class HeatmapSpecMetric:
    metric_key: str
    score_run_id: UUID
    weight: float


@dataclass(frozen=True)
class HeatmapSpec:
    grid_version: str
    metrics: tuple[HeatmapSpecMetric, ...]


@dataclass(frozen=True)
class PreparedHeatmap:
    grid_version: str
    weights: dict[str, float]
    scoring_signature: str
    spec: str
    cell_count: int
    minimum: float
    maximum: float
    mean: float
    tile_url_template: str
    delivery_version: str = HEATMAP_DELIVERY_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "grid_version": self.grid_version,
            "weights": self.weights,
            "scoring_signature": self.scoring_signature,
            "spec": self.spec,
            "cell_count": self.cell_count,
            "min": self.minimum,
            "max": self.maximum,
            "mean": self.mean,
            "tile_url_template": self.tile_url_template,
            "delivery_version": self.delivery_version,
        }


@dataclass(frozen=True)
class HeatmapTile:
    payload: bytes
    etag: str
    scoring_signature: str


def encode_heatmap_spec(plan: ScoringPlan) -> str:
    payload = {
        "version": HEATMAP_SPEC_VERSION,
        "grid_version": plan.grid_version,
        "metrics": [
            {
                "metric_key": metric.metric_key,
                "score_run_id": str(metric.score_run_id),
                "weight": float(metric.weight).hex(),
            }
            for metric in plan.metrics
        ],
    }
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode()
    if len(canonical) > MAX_DECODED_SPEC_BYTES:
        raise HeatmapError("heatmap spec is too large")
    return base64.urlsafe_b64encode(canonical).rstrip(b"=").decode("ascii")


def decode_heatmap_spec(encoded: str) -> HeatmapSpec:
    if not encoded or len(encoded) > MAX_DECODED_SPEC_BYTES * 2:
        raise HeatmapError("invalid heatmap spec size")
    if re.fullmatch(r"[A-Za-z0-9_-]+", encoded) is None:
        raise HeatmapError("invalid base64url heatmap spec")
    try:
        padding = "=" * (-len(encoded) % 4)
        decoded = base64.b64decode(
            encoded + padding, altchars=b"-_", validate=True
        )
    except (ValueError, binascii.Error) as exc:
        raise HeatmapError("invalid base64url heatmap spec") from exc
    if len(decoded) > MAX_DECODED_SPEC_BYTES:
        raise HeatmapError("heatmap spec is too large")
    try:
        payload = json.loads(decoded.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HeatmapError("malformed heatmap spec") from exc
    if not isinstance(payload, dict) or payload.get("version") != HEATMAP_SPEC_VERSION:
        raise HeatmapError("unsupported heatmap spec version")
    if set(payload) != {"version", "grid_version", "metrics"}:
        raise HeatmapError("malformed heatmap spec")
    grid_version = payload.get("grid_version")
    raw_metrics = payload.get("metrics")
    if not isinstance(grid_version, str) or not grid_version.strip():
        raise HeatmapError("invalid heatmap grid version")
    if not isinstance(raw_metrics, list) or not 1 <= len(raw_metrics) <= MAX_HEATMAP_METRICS:
        raise HeatmapError("heatmap spec must contain between 1 and 12 metrics")
    metrics: list[HeatmapSpecMetric] = []
    seen_keys: set[str] = set()
    for raw_metric in raw_metrics:
        if not isinstance(raw_metric, dict) or set(raw_metric) != {
            "metric_key",
            "score_run_id",
            "weight",
        }:
            raise HeatmapError("malformed heatmap metric spec")
        metric_key = raw_metric.get("metric_key")
        if not isinstance(metric_key, str) or not metric_key or metric_key in seen_keys:
            raise HeatmapError("invalid or duplicate heatmap metric key")
        try:
            score_run_id = UUID(str(raw_metric.get("score_run_id")))
            weight = float.fromhex(str(raw_metric.get("weight")))
        except (TypeError, ValueError) as exc:
            raise HeatmapError("invalid heatmap metric identity") from exc
        seen_keys.add(metric_key)
        metrics.append(
            HeatmapSpecMetric(
                metric_key=metric_key,
                score_run_id=score_run_id,
                weight=weight,
            )
        )
    return HeatmapSpec(grid_version=grid_version, metrics=tuple(metrics))


class HeatmapService:
    def __init__(self, engine: Engine, scoring: ScoringService) -> None:
        self._engine = engine
        self._scoring = scoring

    def prepare(self, grid_version: str, weights: dict[str, float]) -> PreparedHeatmap:
        try:
            plan = self._scoring.resolve_current_plan(grid_version, weights)
            result = self._scoring.evaluate_plan(plan, limit=1)
        except ScoringError as exc:
            raise HeatmapError(str(exc)) from exc
        spec = encode_heatmap_spec(plan)
        return PreparedHeatmap(
            grid_version=plan.grid_version,
            weights=plan.weights,
            scoring_signature=plan.scoring_signature,
            spec=spec,
            cell_count=result.cell_count,
            minimum=result.minimum,
            maximum=result.maximum,
            mean=result.mean,
            tile_url_template=(
                f"/api/analysis/heatmap/tiles/{plan.scoring_signature}/"
                f"{{z}}/{{x}}/{{y}}.mvt?spec={spec}"
            ),
        )

    def plan_from_spec(self, encoded_spec: str) -> ScoringPlan:
        spec = decode_heatmap_spec(encoded_spec)
        weights = {metric.metric_key: metric.weight for metric in spec.metrics}
        run_ids = {metric.metric_key: metric.score_run_id for metric in spec.metrics}
        try:
            plan = self._scoring.resolve_historical_plan(
                spec.grid_version, weights, run_ids
            )
        except ScoringError as exc:
            raise HeatmapError(str(exc)) from exc
        if encode_heatmap_spec(plan) != encoded_spec:
            raise HeatmapError("heatmap spec is not canonical")
        return plan

    def tile(
        self,
        scoring_signature: str,
        z: int,
        x: int,
        y: int,
        encoded_spec: str,
    ) -> HeatmapTile:
        plan = self.plan_from_spec(encoded_spec)
        if plan.scoring_signature != scoring_signature:
            raise HeatmapError("scoring signature does not match heatmap spec")
        statement, params = self.tile_statement(plan, z, x, y)
        with self._engine.connect() as connection:
            payload = connection.scalar(statement, params)
        etag_payload = f"{HEATMAP_DELIVERY_VERSION}:{scoring_signature}:{z}:{x}:{y}"
        etag = hashlib.sha256(etag_payload.encode()).hexdigest()
        return HeatmapTile(
            payload=b"" if payload is None else bytes(payload),
            etag=etag,
            scoring_signature=scoring_signature,
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
            "total_weight": plan.total_weight,
        }
        selected_rows: list[str] = []
        for index, metric in enumerate(plan.metrics):
            selected_rows.append(
                f"(CAST(:run_{index} AS uuid), CAST(:weight_{index} AS double precision))"
            )
            params[f"run_{index}"] = str(metric.score_run_id)
            params[f"weight_{index}"] = metric.weight
        statement = text(
            "WITH tile AS ("
            "SELECT ST_TileEnvelope(:z, :x, :y) AS bounds"
            "), tile_cells AS MATERIALIZED ("
            "SELECT cell.cell_id, cell.district_id, cell.geom, tile.bounds "
            "FROM analytics.analysis_cells AS cell CROSS JOIN tile "
            "WHERE cell.grid_version = :grid_version "
            "AND cell.geom && ST_Transform(tile.bounds, 4326) "
            "AND ST_Intersects(ST_Transform(cell.geom, 3857), tile.bounds)"
            "), selected(score_run_id, weight) AS (VALUES "
            + ",".join(selected_rows)
            + "), scored AS ("
            "SELECT cell.cell_id, cell.district_id, cell.geom, cell.bounds, "
            "(sum(score.score::numeric * selected.weight::numeric) / "
            "CAST(:total_weight AS numeric))::double precision AS score "
            "FROM tile_cells AS cell "
            "JOIN analytics.cell_metric_scores AS score ON score.cell_id = cell.cell_id "
            "JOIN selected ON selected.score_run_id = score.score_run_id "
            "GROUP BY cell.cell_id, cell.district_id, cell.geom, cell.bounds"
            "), tile_rows AS MATERIALIZED ("
            "SELECT cell_id, district_id::text AS district_id, score, "
            "ST_AsMVTGeom(ST_Transform(geom, 3857), bounds, 4096, 64, true) AS geom "
            "FROM scored ORDER BY cell_id"
            ") SELECT ST_AsMVT(tile_rows, 'analysis_heatmap', 4096, 'geom') FROM tile_rows"
        )
        return statement, params
