from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import Engine, text

from app.analytics.heatmap import HeatmapError, HeatmapService
from app.analytics.metrics.registry import MetricRegistry
from app.analytics.scoring.engine import ScoringService


class ScenarioExplanationError(ValueError):
    """Raised when an immutable heatmap cell cannot be explained."""


@dataclass(frozen=True)
class ExplanationTarget:
    object_id: UUID
    name: str | None
    geometry_type: str
    distance_m: float
    area_m2: float | None


@dataclass(frozen=True)
class ExplanationFactor:
    metric_key: str
    label: str
    weight: float
    individual_score: float
    contribution: float
    target: ExplanationTarget | None


@dataclass(frozen=True)
class ScenarioExplanation:
    grid_version: str
    cell_id: str
    scoring_signature: str
    score: float
    factors: tuple[ExplanationFactor, ...]


_SCORE_SQL = text(
    """
    SELECT score
    FROM analytics.cell_metric_scores
    WHERE score_run_id = :score_run_id AND cell_id = :cell_id
    """
)

_CELL_SQL = text(
    """
    SELECT center_metric
    FROM analytics.analysis_cells
    WHERE cell_id = :cell_id AND grid_version = :grid_version
    """
)

_RUN_DEFINITION_SQL = text(
    """
    SELECT
        metric.definition_snapshot,
        current_score.score_run_id IS NOT NULL
          AND current_metric.run_id IS NOT NULL AS is_current
    FROM analytics.metric_score_runs AS score
    JOIN analytics.metric_runs AS metric ON metric.run_id = score.metric_run_id
    LEFT JOIN analytics.metric_score_current_runs AS current_score
      ON current_score.metric_key = score.metric_key
     AND current_score.grid_version = score.grid_version
     AND current_score.score_run_id = score.score_run_id
    LEFT JOIN analytics.metric_current_runs AS current_metric
      ON current_metric.metric_key = metric.metric_key
     AND current_metric.grid_version = metric.grid_version
     AND current_metric.run_id = metric.run_id
    WHERE score.score_run_id = :score_run_id
    """
)

_TARGET_SQL = text(
    """
    WITH category_objects AS MATERIALIZED (
        SELECT object.id AS object_id
        FROM catalog.object_categories AS assignment
        JOIN catalog.objects AS object
          ON object.id = assignment.object_id
         AND object.lifecycle_status = 'active'
         AND object.geom IS NOT NULL
        WHERE assignment.category_key = :category_key
          AND assignment.lifecycle_status = 'active'
    ),
    facility_members AS MATERIALIZED (
        SELECT
            object.object_id,
            facility.id AS facility_id,
            facility.analysis_object_id
        FROM category_objects AS object
        JOIN domain.facility_entity_members AS member
          ON member.canonical_object_id = object.object_id
         AND member.lifecycle_status = 'active'
        JOIN domain.facility_entities AS facility
          ON facility.id = member.facility_entity_id
         AND facility.lifecycle_status = 'active'
         AND facility.category_key = :category_key
    ),
    logical_targets AS (
        SELECT DISTINCT facility_id AS logical_target_id, analysis_object_id
        FROM facility_members
        UNION ALL
        SELECT object.object_id, object.object_id
        FROM category_objects AS object
        WHERE NOT EXISTS (
            SELECT 1 FROM facility_members AS member
            WHERE member.object_id = object.object_id
        )
    ),
    target_geometry AS (
        SELECT
            target.logical_target_id,
            object.id AS object_id,
            object.name,
            GeometryType(object.geom) AS geometry_type,
            ST_Transform(object.geom, 32636) AS geom_metric,
            CASE
                WHEN GeometryType(object.geom) IN ('POLYGON', 'MULTIPOLYGON')
                THEN ST_Area(ST_Transform(object.geom, 32636))
            END AS area_m2
        FROM logical_targets AS target
        JOIN catalog.objects AS object
          ON object.id = target.analysis_object_id
         AND object.lifecycle_status = 'active'
         AND object.geom IS NOT NULL
    )
    SELECT
        target.object_id,
        target.name,
        target.geometry_type,
        ST_Distance(target.geom_metric, cell.center_metric) AS distance_m,
        target.area_m2
    FROM analytics.analysis_cells AS cell
    CROSS JOIN target_geometry AS target
    WHERE cell.cell_id = :cell_id
      AND cell.grid_version = :grid_version
    ORDER BY
        ln(GREATEST(CASE :quality_model
            WHEN 'park' THEN (
                :minimum_size_quality
                + (1.0 - :minimum_size_quality)
                  * (1.0 - exp(GREATEST(
                      CAST(-coalesce(target.area_m2, 0.0) / :area_reference_m2
                           AS double precision),
                      CAST(-700.0 AS double precision)
                  )))
            )
            WHEN 'water' THEN CASE
                WHEN target.geometry_type IN ('POLYGON', 'MULTIPOLYGON') THEN (
                    :minimum_size_quality
                    + (1.0 - :minimum_size_quality)
                      * (1.0 - exp(GREATEST(
                          CAST(-coalesce(target.area_m2, 0.0) / :area_reference_m2
                               AS double precision),
                          CAST(-700.0 AS double precision)
                      )))
                )
                ELSE :line_quality
            END
            ELSE 1.0
        END, CAST(1e-300 AS double precision)))
        - CAST(0.6931471805599453 AS double precision) * power(
            CAST(
                ST_Distance(target.geom_metric, cell.center_metric)
                / :half_distance_m AS double precision
            ),
            CAST(2.0 AS double precision)
        ) DESC,
        target.logical_target_id
    LIMIT 1
    """
)


class ScenarioExplanationService:
    def __init__(
        self,
        engine: Engine,
        scoring: ScoringService,
        metrics: MetricRegistry,
    ) -> None:
        self._engine = engine
        self._heatmap = HeatmapService(engine, scoring)
        self._metrics = metrics

    def explain(self, cell_id: str, encoded_spec: str) -> ScenarioExplanation:
        try:
            plan = self._heatmap.plan_from_spec(encoded_spec)
        except HeatmapError as exc:
            raise ScenarioExplanationError(str(exc)) from exc
        total_weight = plan.total_weight
        factors: list[ExplanationFactor] = []
        with self._engine.connect() as connection:
            if connection.scalar(
                _CELL_SQL,
                {"cell_id": cell_id, "grid_version": plan.grid_version},
            ) is None:
                raise ScenarioExplanationError("analysis cell not found for heatmap grid")
            for planned in plan.metrics:
                score = connection.scalar(
                    _SCORE_SQL,
                    {"score_run_id": planned.score_run_id, "cell_id": cell_id},
                )
                if score is None:
                    raise ScenarioExplanationError(
                        f"cell score is missing for metric: {planned.metric_key}"
                    )
                definition = self._metrics.get(planned.metric_key)
                if definition is None:
                    raise ScenarioExplanationError(
                        f"metric definition is missing: {planned.metric_key}"
                    )
                run = connection.execute(
                    _RUN_DEFINITION_SQL,
                    {"score_run_id": planned.score_run_id},
                ).mappings().one_or_none()
                if run is None or not isinstance(run["definition_snapshot"], dict):
                    raise ScenarioExplanationError(
                        f"metric run definition is missing: {planned.metric_key}"
                    )
                definition_snapshot = run["definition_snapshot"]
                provider_key = definition_snapshot.get("provider_key")
                provider_config = definition_snapshot.get("provider_config")
                if not isinstance(provider_config, dict):
                    provider_config = {}
                category_key = provider_config.get("category_key")
                target = None
                if isinstance(category_key, str) and bool(run["is_current"]):
                    radius = provider_config.get("half_distance_m")
                    if not isinstance(radius, int | float) or radius <= 0:
                        radius = provider_config.get("radius_m", 1000.0)
                    quality_model = (
                        "park"
                        if provider_key == "catalog.park_accessibility"
                        else "water"
                        if provider_key == "catalog.water_accessibility"
                        else "nearest"
                    )
                    row = connection.execute(
                        _TARGET_SQL,
                        {
                            "category_key": category_key,
                            "cell_id": cell_id,
                            "grid_version": plan.grid_version,
                            "quality_model": quality_model,
                            "half_distance_m": float(radius),
                            "area_reference_m2": float(
                                provider_config.get("area_reference_m2", 1.0)
                            ),
                            "minimum_size_quality": float(
                                provider_config.get("minimum_size_quality", 0.0)
                            ),
                            "line_quality": float(provider_config.get("line_quality", 1.0)),
                        },
                    ).one_or_none()
                    if row is not None:
                        mapping: Any = row
                        target = ExplanationTarget(
                            object_id=mapping.object_id,
                            name=mapping.name,
                            geometry_type=str(mapping.geometry_type),
                            distance_m=float(mapping.distance_m),
                            area_m2=(
                                None if mapping.area_m2 is None else float(mapping.area_m2)
                            ),
                        )
                individual_score = float(score)
                contribution = individual_score * planned.weight / total_weight
                factors.append(
                    ExplanationFactor(
                        metric_key=planned.metric_key,
                        label=definition.label,
                        weight=planned.weight,
                        individual_score=individual_score,
                        contribution=contribution,
                        target=target,
                    )
                )
        return ScenarioExplanation(
            grid_version=plan.grid_version,
            cell_id=cell_id,
            scoring_signature=plan.scoring_signature,
            score=sum(item.contribution for item in factors),
            factors=tuple(factors),
        )
