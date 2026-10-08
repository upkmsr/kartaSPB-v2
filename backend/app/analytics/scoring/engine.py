import hashlib
import json
import math
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import Engine, bindparam, text

from app.analytics.scoring.registry import NormalizationRegistry


class ScoringError(ValueError):
    """Raised when an explicit scoring request cannot be evaluated."""


@dataclass(frozen=True)
class ScoredCell:
    cell_id: str
    score: float
    district_id: UUID


@dataclass(frozen=True)
class ScoringMetric:
    metric_key: str
    score_run_id: UUID
    run_signature: str
    weight: float


@dataclass(frozen=True)
class ScoringPlan:
    grid_version: str
    metrics: tuple[ScoringMetric, ...]
    scoring_signature: str
    cell_count: int
    total_weight: float

    @property
    def weights(self) -> dict[str, float]:
        return {metric.metric_key: metric.weight for metric in self.metrics}


@dataclass(frozen=True)
class ScoringResult:
    grid_version: str
    weights: dict[str, float]
    scoring_signature: str
    cell_count: int
    minimum: float
    maximum: float
    mean: float
    top_cells: tuple[ScoredCell, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "grid_version": self.grid_version,
            "weights": self.weights,
            "scoring_signature": self.scoring_signature,
            "cell_count": self.cell_count,
            "min": self.minimum,
            "max": self.maximum,
            "mean": self.mean,
            "top_cells": [
                {
                    "cell_id": cell.cell_id,
                    "score": cell.score,
                    "district_id": str(cell.district_id),
                }
                for cell in self.top_cells
            ],
        }


def validate_weights(
    weights: dict[str, float], registry: NormalizationRegistry
) -> dict[str, float]:
    if not weights:
        raise ScoringError("at least one positive weight is required")
    normalized: dict[str, float] = {}
    for metric_key, raw_weight in weights.items():
        if registry.get(metric_key) is None:
            raise ScoringError(f"unknown or disabled metric: {metric_key}")
        if isinstance(raw_weight, bool):
            raise ScoringError(f"weight must be numeric: {metric_key}")
        weight = float(raw_weight)
        if not math.isfinite(weight):
            raise ScoringError(f"weight must be finite: {metric_key}")
        if not 0 <= weight <= 100:
            raise ScoringError(f"weight must be between 0 and 100: {metric_key}")
        normalized[metric_key] = weight
    selected = {key: normalized[key] for key in sorted(normalized) if normalized[key] > 0}
    if not selected:
        raise ScoringError("at least one positive weight is required")
    return selected


class ScoringService:
    def __init__(self, engine: Engine, registry: NormalizationRegistry) -> None:
        self._engine = engine
        self._registry = registry

    def resolve_current_plan(
        self,
        grid_version: str,
        weights: dict[str, float],
    ) -> ScoringPlan:
        if not grid_version.strip():
            raise ScoringError("grid_version must not be blank")
        selected_weights = validate_weights(weights, self._registry)
        metric_keys = tuple(selected_weights)
        with self._engine.connect() as connection:
            rows = connection.execute(
                text(
                    "SELECT c.metric_key, r.score_run_id, r.run_signature, "
                    "r.normalization_checksum, r.cell_count "
                    "FROM analytics.metric_score_current_runs AS c "
                    "JOIN analytics.metric_score_runs AS r "
                    "ON r.score_run_id = c.score_run_id "
                    "WHERE c.grid_version = :grid_version AND c.metric_key IN :metric_keys "
                ).bindparams(bindparam("metric_keys", expanding=True)),
                {"grid_version": grid_version, "metric_keys": metric_keys},
            ).mappings().all()
            by_key = {row["metric_key"]: row for row in rows}
            missing = [key for key in metric_keys if key not in by_key]
            if missing:
                raise ScoringError(
                    f"current normalized score run not found: {', '.join(missing)}"
                )
            stale: list[str] = []
            for key in metric_keys:
                definition = self._registry.get(key)
                assert definition is not None
                if by_key[key]["normalization_checksum"] != definition.checksum():
                    stale.append(key)
            if stale:
                raise ScoringError(
                    "current normalized score run does not match enabled normalization: "
                    + ", ".join(stale)
                )
        return self._build_plan(grid_version, selected_weights, by_key)

    def resolve_historical_plan(
        self,
        grid_version: str,
        weights: dict[str, float],
        score_run_ids: dict[str, UUID],
    ) -> ScoringPlan:
        if not grid_version.strip():
            raise ScoringError("grid_version must not be blank")
        selected_weights = validate_weights(weights, self._registry)
        if set(selected_weights) != set(score_run_ids):
            raise ScoringError("score run keys must match selected weight keys")
        run_ids = tuple(score_run_ids[key] for key in selected_weights)
        with self._engine.connect() as connection:
            rows = connection.execute(
                text(
                    "SELECT r.metric_key, r.score_run_id, r.run_signature, r.cell_count, "
                    "r.grid_version "
                    "FROM analytics.metric_score_runs AS r "
                    "WHERE r.score_run_id IN :run_ids "
                ).bindparams(bindparam("run_ids", expanding=True)),
                {"run_ids": run_ids},
            ).mappings().all()
        by_id = {row["score_run_id"]: row for row in rows}
        by_key: dict[str, Any] = {}
        for metric_key, score_run_id in score_run_ids.items():
            row = by_id.get(score_run_id)
            if row is None:
                raise ScoringError(f"normalized score run not found: {score_run_id}")
            if row["metric_key"] != metric_key:
                raise ScoringError(f"normalized score run does not belong to metric: {metric_key}")
            if row["grid_version"] != grid_version:
                raise ScoringError("normalized score run belongs to a different grid")
            by_key[metric_key] = row
        return self._build_plan(grid_version, selected_weights, by_key)

    @staticmethod
    def _build_plan(
        grid_version: str,
        selected_weights: dict[str, float],
        by_key: dict[str, Any],
    ) -> ScoringPlan:
        metric_keys = tuple(selected_weights)
        cell_counts = {int(by_key[key]["cell_count"]) for key in metric_keys}
        if len(cell_counts) != 1:
            raise ScoringError("normalized score run is incomplete")
        metrics = tuple(
            ScoringMetric(
                metric_key=key,
                score_run_id=by_key[key]["score_run_id"],
                run_signature=by_key[key]["run_signature"],
                weight=selected_weights[key],
            )
            for key in metric_keys
        )
        signature_payload = {
            "grid_version": grid_version,
            "metrics": [
                {
                    "metric_key": metric.metric_key,
                    "run_signature": metric.run_signature,
                    "weight": metric.weight.hex(),
                }
                for metric in metrics
            ],
        }
        canonical = json.dumps(signature_payload, sort_keys=True, separators=(",", ":"))
        return ScoringPlan(
            grid_version=grid_version,
            metrics=metrics,
            scoring_signature=hashlib.sha256(canonical.encode()).hexdigest(),
            cell_count=next(iter(cell_counts)),
            total_weight=math.fsum(selected_weights.values()),
        )

    def evaluate(
        self,
        grid_version: str,
        weights: dict[str, float],
        *,
        limit: int = 20,
    ) -> ScoringResult:
        plan = self.resolve_current_plan(grid_version, weights)
        return self.evaluate_plan(plan, limit=limit)

    def evaluate_plan(self, plan: ScoringPlan, *, limit: int = 20) -> ScoringResult:
        if not 1 <= limit <= 100:
            raise ScoringError("limit must be between 1 and 100")
        params: dict[str, object] = {
            "grid_version": plan.grid_version,
            "total_weight": plan.total_weight,
            "limit": limit,
        }
        value_rows: list[str] = []
        for index, metric in enumerate(plan.metrics):
            value_rows.append(
                f"(CAST(:run_{index} AS uuid), CAST(:weight_{index} AS double precision))"
            )
            params[f"run_{index}"] = str(metric.score_run_id)
            params[f"weight_{index}"] = metric.weight
        query = text(
            "WITH selected(score_run_id, weight) AS (VALUES "
            + ",".join(value_rows)
            + "), scored AS ("
            "SELECT s.cell_id, a.district_id, "
            "sum(s.score * selected.weight) / :total_weight AS score "
            "FROM selected JOIN analytics.cell_metric_scores AS s "
            "ON s.score_run_id = selected.score_run_id "
            "JOIN analytics.analysis_cells AS a ON a.cell_id = s.cell_id "
            "WHERE a.grid_version = :grid_version "
            "GROUP BY s.cell_id, a.district_id"
            "), summarized AS ("
            "SELECT cell_id, district_id, score, count(*) OVER () AS cell_count, "
            "min(score) OVER () AS minimum, max(score) OVER () AS maximum, "
            "avg(score) OVER () AS mean FROM scored"
            ") SELECT * FROM summarized ORDER BY score DESC, cell_id LIMIT :limit"
        )
        with self._engine.connect() as connection:
            result_rows = connection.execute(query, params).mappings().all()
        if not result_rows:
            raise ScoringError("scoring produced no cells")
        first = result_rows[0]
        if int(first["cell_count"]) != plan.cell_count:
            raise ScoringError("scoring result is incomplete")
        return ScoringResult(
            grid_version=plan.grid_version,
            weights=plan.weights,
            scoring_signature=plan.scoring_signature,
            cell_count=int(first["cell_count"]),
            minimum=float(first["minimum"]),
            maximum=float(first["maximum"]),
            mean=float(first["mean"]),
            top_cells=tuple(
                ScoredCell(
                    cell_id=row["cell_id"],
                    score=float(row["score"]),
                    district_id=row["district_id"],
                )
                for row in result_rows
            ),
        )
