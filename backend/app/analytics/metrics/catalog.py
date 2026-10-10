import hashlib
import json
import math
from time import monotonic
from typing import Any, cast

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import Connection, text

from app.analytics.metrics.providers import MetricCalculation, MetricProviderContext

METRIC_SRID = 32636
DISPLAY_SRID = 4326


class MetricProviderError(RuntimeError):
    """Raised when provider configuration or analytical source state is invalid."""


class CatalogNearestDistanceConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    category_key: str

    @field_validator("category_key")
    @classmethod
    def category_must_be_dotted(cls, value: str) -> str:
        if "." not in value or value != value.strip().lower():
            raise ValueError("category_key must be a lowercase dotted key")
        return value


class CatalogCountWithinRadiusConfig(CatalogNearestDistanceConfig):
    radius_m: float = Field(gt=0)


class CatalogSmoothInfluenceConfig(CatalogNearestDistanceConfig):
    radius_m: float = Field(gt=0)


class CatalogPrimaryAccessibilityConfig(CatalogNearestDistanceConfig):
    half_distance_m: float = Field(gt=0)
    cutoff_multiplier: float = Field(default=4.0, ge=3.0, le=6.0)
    extra_bonus_cap: float = Field(default=0.2, ge=0.0, le=0.35)
    extra_saturation: float = Field(default=1.0, gt=0)


class CatalogParkAccessibilityConfig(CatalogPrimaryAccessibilityConfig):
    area_reference_m2: float = Field(gt=0)
    minimum_size_quality: float = Field(ge=0.0, lt=1.0)


class CatalogWaterAccessibilityConfig(CatalogPrimaryAccessibilityConfig):
    area_reference_m2: float = Field(gt=0)
    minimum_size_quality: float = Field(ge=0.0, lt=1.0)
    line_quality: float = Field(gt=0.0, le=1.0)


def smooth_influence(distance_m: float, radius_m: float) -> float:
    """Compact quartic influence with a smooth zero derivative at support."""
    if not math.isfinite(distance_m) or distance_m < 0:
        raise ValueError("distance_m must be finite and non-negative")
    if not math.isfinite(radius_m) or radius_m <= 0:
        raise ValueError("radius_m must be finite and positive")
    if distance_m >= radius_m:
        return 0.0
    ratio = distance_m / radius_m
    return (1.0 - ratio * ratio) ** 2


def proximity_influence(distance_m: float, half_distance_m: float) -> float:
    """Unbounded Gaussian-like tail whose value is 0.5 at the configured distance."""
    if not math.isfinite(distance_m) or distance_m < 0:
        raise ValueError("distance_m must be finite and non-negative")
    if not math.isfinite(half_distance_m) or half_distance_m <= 0:
        raise ValueError("half_distance_m must be finite and positive")
    return math.exp(-math.log(2.0) * (distance_m / half_distance_m) ** 2)


def size_quality(area_m2: float, reference_m2: float, minimum: float) -> float:
    """Diminishing-return geometry quality for area-backed amenities."""
    if not math.isfinite(area_m2) or area_m2 < 0:
        raise ValueError("area_m2 must be finite and non-negative")
    if not math.isfinite(reference_m2) or reference_m2 <= 0:
        raise ValueError("reference_m2 must be finite and positive")
    if not math.isfinite(minimum) or not 0 <= minimum < 1:
        raise ValueError("minimum must satisfy 0 <= minimum < 1")
    return minimum + (1.0 - minimum) * (1.0 - math.exp(-area_m2 / reference_m2))


def bounded_accessibility(
    primary: float,
    total: float,
    bonus_cap: float,
    bonus_saturation: float,
) -> float:
    """Keep nearest/strongest access primary and bound all additional availability."""
    extra = max(total - primary, 0.0)
    bonus = bonus_cap * (1.0 - math.exp(-extra / bonus_saturation))
    return primary + (1.0 - primary) * bonus


_CREATE_TARGETS_SQL = text(
    """
    CREATE TEMPORARY TABLE f8_metric_targets ON COMMIT DROP AS
    WITH category_objects AS MATERIALIZED (
        SELECT o.id AS object_id, o.geom
        FROM catalog.object_categories AS assignment
        JOIN catalog.objects AS o ON o.id = assignment.object_id
        WHERE assignment.category_key = :category_key
          AND assignment.lifecycle_status = 'active'
          AND o.lifecycle_status = 'active'
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
    facility_targets AS (
        SELECT
            'facility'::text AS target_kind,
            facility_id AS logical_target_id,
            analysis_object_id,
            array_agg(DISTINCT object_id ORDER BY object_id) AS source_object_ids
        FROM facility_members
        GROUP BY facility_id, analysis_object_id
    ),
    ordinary_targets AS (
        SELECT
            'object'::text AS target_kind,
            object.object_id AS logical_target_id,
            object.object_id AS analysis_object_id,
            ARRAY[object.object_id]::uuid[] AS source_object_ids
        FROM category_objects AS object
        WHERE NOT EXISTS (
            SELECT 1
            FROM facility_members AS member
            WHERE member.object_id = object.object_id
        )
    ),
    logical_targets AS (
        SELECT * FROM facility_targets
        UNION ALL
        SELECT * FROM ordinary_targets
    )
    SELECT
        target.target_kind,
        target.logical_target_id,
        target.analysis_object_id,
        target.source_object_ids,
        analysis.lifecycle_status AS analysis_lifecycle_status,
        analysis.geom AS geom_display,
        GeometryType(analysis.geom) AS geometry_type,
        CASE
            WHEN GeometryType(analysis.geom) IN ('POLYGON', 'MULTIPOLYGON')
            THEN ST_Area(ST_Transform(analysis.geom, :metric_srid))
            ELSE 0.0
        END AS area_m2,
        CASE
            WHEN analysis.geom IS NOT NULL AND ST_SRID(analysis.geom) = :display_srid
            THEN ST_Transform(analysis.geom, :metric_srid)
        END AS geom_metric
    FROM logical_targets AS target
    LEFT JOIN catalog.objects AS analysis ON analysis.id = target.analysis_object_id
    """
)

_TARGET_VALIDATION_SQL = text(
    """
    SELECT
        count(*) AS target_count,
        count(*) - count(DISTINCT (target_kind, logical_target_id)) AS duplicate_count,
        count(*) FILTER (
            WHERE analysis_lifecycle_status IS DISTINCT FROM 'active'
               OR geom_display IS NULL
               OR ST_IsEmpty(geom_display)
               OR NOT ST_IsValid(geom_display)
               OR ST_SRID(geom_display) <> :display_srid
               OR geom_metric IS NULL
               OR ST_IsEmpty(geom_metric)
               OR NOT ST_IsValid(geom_metric)
               OR ST_SRID(geom_metric) <> :metric_srid
        ) AS invalid_count
    FROM f8_metric_targets
    """
)

_NEAREST_SQL = text(
    """
    SELECT cell.cell_id, nearest.raw_value
    FROM analytics.analysis_cells AS cell
    CROSS JOIN LATERAL (
        SELECT ST_Distance(cell.center_metric, target.geom_metric) AS raw_value
        FROM f8_metric_targets AS target
        ORDER BY target.geom_metric <-> cell.center_metric
        LIMIT 1
    ) AS nearest
    WHERE cell.grid_version = :grid_version
    ORDER BY cell.cell_id
    """
)

_COUNT_SQL = text(
    """
    SELECT cell.cell_id, matches.raw_value
    FROM analytics.analysis_cells AS cell
    CROSS JOIN LATERAL (
        SELECT count(*)::double precision AS raw_value
        FROM f8_metric_targets AS target
        WHERE ST_DWithin(target.geom_metric, cell.center_metric, :radius_m)
    ) AS matches
    WHERE cell.grid_version = :grid_version
    ORDER BY cell.cell_id
    """
)

_SMOOTH_INFLUENCE_SQL = text(
    """
    SELECT
        cell.cell_id,
        coalesce(sum(power(1.0 - power(match.distance_m / :radius_m, 2), 2)), 0.0)
            AS raw_value,
        count(match.distance_m) AS match_count
    FROM analytics.analysis_cells AS cell
    LEFT JOIN LATERAL (
        SELECT ST_Distance(cell.center_metric, target.geom_metric) AS distance_m
        FROM f8_metric_targets AS target
        WHERE ST_DWithin(target.geom_metric, cell.center_metric, :radius_m)
    ) AS match ON true
    WHERE cell.grid_version = :grid_version
    GROUP BY cell.cell_id
    ORDER BY cell.cell_id
    """
)

_PRIMARY_ACCESSIBILITY_SQL = text(
    """
    SELECT
        cell.cell_id,
        coalesce(match.primary_influence, 0.0)
          + (1.0 - coalesce(match.primary_influence, 0.0))
            * :extra_bonus_cap
            * (1.0 - exp(
                -greatest(
                    coalesce(match.total_influence, 0.0)
                    - coalesce(match.primary_influence, 0.0),
                    0.0
                ) / :extra_saturation
            )) AS raw_value,
        coalesce(match.match_count, 0) AS match_count
    FROM analytics.analysis_cells AS cell
    LEFT JOIN LATERAL (
        SELECT
            max(candidate.influence) AS primary_influence,
            sum(candidate.influence) AS total_influence,
            count(*) AS match_count
        FROM (
            SELECT exp(
                -ln(2.0) * power(
                    ST_Distance(cell.center_metric, target.geom_metric)
                    / :half_distance_m,
                    2
                )
            ) AS influence
            FROM f8_metric_targets AS target
            WHERE ST_DWithin(
                target.geom_metric,
                cell.center_metric,
                :cutoff_distance_m
            )
        ) AS candidate
    ) AS match ON true
    WHERE cell.grid_version = :grid_version
    ORDER BY cell.cell_id
    """
)

_PARK_ACCESSIBILITY_SQL = text(
    """
    SELECT
        cell.cell_id,
        coalesce(match.primary_influence, 0.0)
          + (1.0 - coalesce(match.primary_influence, 0.0))
            * :extra_bonus_cap
            * (1.0 - exp(
                -greatest(
                    coalesce(match.total_influence, 0.0)
                    - coalesce(match.primary_influence, 0.0),
                    0.0
                ) / :extra_saturation
            )) AS raw_value,
        coalesce(match.match_count, 0) AS match_count
    FROM analytics.analysis_cells AS cell
    LEFT JOIN LATERAL (
        SELECT
            max(candidate.influence) AS primary_influence,
            sum(candidate.influence) AS total_influence,
            count(*) AS match_count
        FROM (
            SELECT
                (
                    :minimum_size_quality
                    + (1.0 - :minimum_size_quality)
                      * (1.0 - exp(-target.area_m2 / :area_reference_m2))
                )
                * exp(
                    -ln(2.0) * power(
                        ST_Distance(cell.center_metric, target.geom_metric)
                        / :half_distance_m,
                        2
                    )
                ) AS influence
            FROM f8_metric_targets AS target
            WHERE ST_DWithin(
                target.geom_metric,
                cell.center_metric,
                :cutoff_distance_m
            )
        ) AS candidate
    ) AS match ON true
    WHERE cell.grid_version = :grid_version
    ORDER BY cell.cell_id
    """
)

_WATER_ACCESSIBILITY_SQL = text(
    """
    SELECT
        cell.cell_id,
        coalesce(match.primary_influence, 0.0) AS raw_value,
        coalesce(match.match_count, 0) AS match_count
    FROM analytics.analysis_cells AS cell
    LEFT JOIN LATERAL (
        SELECT
            max(
                CASE
                    WHEN target.geometry_type IN ('POLYGON', 'MULTIPOLYGON')
                    THEN (
                        :minimum_size_quality
                        + (1.0 - :minimum_size_quality)
                          * (1.0 - exp(-target.area_m2 / :area_reference_m2))
                    )
                    ELSE :line_quality
                END
                * exp(
                    -ln(2.0) * power(
                        ST_Distance(cell.center_metric, target.geom_metric)
                        / :half_distance_m,
                        2
                    )
                )
            ) AS primary_influence,
            count(*) AS match_count
        FROM f8_metric_targets AS target
        WHERE ST_DWithin(
            target.geom_metric,
            cell.center_metric,
            :cutoff_distance_m
        )
    ) AS match ON true
    WHERE cell.grid_version = :grid_version
    ORDER BY cell.cell_id
    """
)


def _grid_checksum(connection: Connection, grid_version: str) -> tuple[str, int]:
    digest = hashlib.sha256()
    count = 0
    rows = connection.execution_options(stream_results=True).execute(
        text(
            "SELECT cell_id, district_id::text, "
            "encode(ST_AsEWKB(geom_metric), 'hex') AS metric_wkb "
            "FROM analytics.analysis_cells WHERE grid_version = :grid_version "
            "ORDER BY cell_id"
        ),
        {"grid_version": grid_version},
    )
    for cell_id, district_id, metric_wkb in rows:
        digest.update(f"{cell_id}\t{district_id}\t{metric_wkb}\n".encode())
        count += 1
    if count == 0:
        raise MetricProviderError(f"grid has no cells: {grid_version}")
    return digest.hexdigest(), count


def _input_fingerprint(
    connection: Connection,
    grid_version: str,
    grid_checksum: str,
    category_key: str,
    *,
    provider_context: dict[str, Any] | None = None,
) -> str:
    digest = hashlib.sha256()
    digest.update(f"grid_version\t{grid_version}\n".encode())
    digest.update(f"grid_checksum\t{grid_checksum}\n".encode())
    digest.update(f"category_key\t{category_key}\n".encode())
    if provider_context is not None:
        canonical_context = json.dumps(
            provider_context, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        )
        digest.update(f"provider_context\t{canonical_context}\n".encode())
    rows = connection.execution_options(stream_results=True).execute(
        text(
            "SELECT target_kind, logical_target_id::text, analysis_object_id::text, "
            "array_to_string(source_object_ids, ','), "
            "encode(ST_AsEWKB(geom_metric), 'hex') "
            "FROM f8_metric_targets "
            "ORDER BY target_kind, logical_target_id, analysis_object_id"
        )
    )
    for target_kind, logical_id, analysis_id, source_ids, metric_wkb in rows:
        digest.update(
            f"{target_kind}\t{logical_id}\t{analysis_id}\t{source_ids}\t{metric_wkb}\n".encode()
        )
    return digest.hexdigest()


def _prepare_targets(
    connection: Connection,
    category_key: str,
    grid_version: str,
    *,
    provider_context: dict[str, Any] | None = None,
) -> tuple[str, int, int]:
    parameters = {
        "category_key": category_key,
        "display_srid": DISPLAY_SRID,
        "metric_srid": METRIC_SRID,
    }
    connection.execute(_CREATE_TARGETS_SQL, parameters)
    validation = connection.execute(_TARGET_VALIDATION_SQL, parameters).one()
    if validation.target_count == 0:
        raise MetricProviderError(f"category has no logical targets: {category_key}")
    if validation.duplicate_count:
        raise MetricProviderError(
            f"category has duplicate logical targets: {category_key} "
            f"({validation.duplicate_count})"
        )
    if validation.invalid_count:
        raise MetricProviderError(
            f"category has invalid analytical target geometries: {category_key} "
            f"({validation.invalid_count})"
        )
    connection.execute(
        text(
            "CREATE UNIQUE INDEX f8_metric_targets_identity_idx "
            "ON f8_metric_targets (target_kind, logical_target_id)"
        )
    )
    connection.execute(
        text(
            "CREATE INDEX f8_metric_targets_geom_gist "
            "ON f8_metric_targets USING gist (geom_metric)"
        )
    )
    connection.execute(text("ANALYZE f8_metric_targets"))
    grid_checksum, grid_cell_count = _grid_checksum(connection, grid_version)
    fingerprint = _input_fingerprint(
        connection,
        grid_version,
        grid_checksum,
        category_key,
        provider_context=provider_context,
    )
    return fingerprint, validation.target_count, grid_cell_count


class CatalogNearestDistanceProvider:
    def calculate(self, context: MetricProviderContext) -> MetricCalculation:
        started = monotonic()
        try:
            config = CatalogNearestDistanceConfig.model_validate(
                context.definition.provider_config
            )
        except ValueError as exc:
            raise MetricProviderError(f"invalid nearest-distance config: {exc}") from exc
        with context.engine.connect().execution_options(
            isolation_level="REPEATABLE READ"
        ) as connection, connection.begin():
            fingerprint, target_count, grid_cell_count = _prepare_targets(
                connection, config.category_key, context.grid_version
            )
            values = tuple(
                (str(cell_id), float(cast(Any, raw_value)))
                for cell_id, raw_value in connection.execute(
                    _NEAREST_SQL, {"grid_version": context.grid_version}
                )
            )
        return MetricCalculation(
            input_fingerprint=fingerprint,
            values=values,
            diagnostics={
                "category_key": config.category_key,
                "target_count": target_count,
                "grid_cell_count": grid_cell_count,
            },
            calculation_duration_seconds=monotonic() - started,
        )


class CatalogCountWithinRadiusProvider:
    def calculate(self, context: MetricProviderContext) -> MetricCalculation:
        started = monotonic()
        try:
            config = CatalogCountWithinRadiusConfig.model_validate(
                context.definition.provider_config
            )
        except ValueError as exc:
            raise MetricProviderError(f"invalid count-radius config: {exc}") from exc
        with context.engine.connect().execution_options(
            isolation_level="REPEATABLE READ"
        ) as connection, connection.begin():
            fingerprint, target_count, grid_cell_count = _prepare_targets(
                connection, config.category_key, context.grid_version
            )
            values = tuple(
                (str(cell_id), float(cast(Any, raw_value)))
                for cell_id, raw_value in connection.execute(
                    _COUNT_SQL,
                    {
                        "grid_version": context.grid_version,
                        "radius_m": config.radius_m,
                    },
                )
            )
        return MetricCalculation(
            input_fingerprint=fingerprint,
            values=values,
            diagnostics={
                "category_key": config.category_key,
                "radius_m": config.radius_m,
                "target_count": target_count,
                "grid_cell_count": grid_cell_count,
            },
            calculation_duration_seconds=monotonic() - started,
        )


class CatalogSmoothInfluenceProvider:
    def calculate(self, context: MetricProviderContext) -> MetricCalculation:
        started = monotonic()
        try:
            config = CatalogSmoothInfluenceConfig.model_validate(
                context.definition.provider_config
            )
        except ValueError as exc:
            raise MetricProviderError(f"invalid smooth-influence config: {exc}") from exc
        provider_context = {
            "provider_key": context.definition.provider_key,
            "calculation_version": context.definition.calculation_version,
            "radius_m": config.radius_m,
        }
        with context.engine.connect().execution_options(
            isolation_level="REPEATABLE READ"
        ) as connection, connection.begin():
            fingerprint, target_count, grid_cell_count = _prepare_targets(
                connection,
                config.category_key,
                context.grid_version,
                provider_context=provider_context,
            )
            rows = connection.execute(
                _SMOOTH_INFLUENCE_SQL,
                {
                    "grid_version": context.grid_version,
                    "radius_m": config.radius_m,
                },
            )
            values: list[tuple[str, float]] = []
            spatial_match_count = 0
            for cell_id, raw_value, match_count in rows:
                values.append((str(cell_id), float(cast(Any, raw_value))))
                spatial_match_count += int(cast(Any, match_count))
        return MetricCalculation(
            input_fingerprint=fingerprint,
            values=tuple(values),
            diagnostics={
                "category_key": config.category_key,
                "radius_m": config.radius_m,
                "kernel": "compact_quartic_v1",
                "target_count": target_count,
                "grid_cell_count": grid_cell_count,
                "spatial_match_count": spatial_match_count,
            },
            calculation_duration_seconds=monotonic() - started,
        )


def _accessibility_parameters(
    config: CatalogPrimaryAccessibilityConfig,
    grid_version: str,
) -> dict[str, object]:
    return {
        "grid_version": grid_version,
        "half_distance_m": config.half_distance_m,
        "cutoff_distance_m": config.half_distance_m * config.cutoff_multiplier,
        "extra_bonus_cap": config.extra_bonus_cap,
        "extra_saturation": config.extra_saturation,
    }


def _accessibility_calculation(
    context: MetricProviderContext,
    config: CatalogPrimaryAccessibilityConfig,
    statement: Any,
    parameters: dict[str, object],
    diagnostics: dict[str, Any],
) -> MetricCalculation:
    started = monotonic()
    provider_context = {
        "provider_key": context.definition.provider_key,
        "calculation_version": context.definition.calculation_version,
        **context.definition.provider_config,
    }
    with context.engine.connect().execution_options(
        isolation_level="REPEATABLE READ"
    ) as connection, connection.begin():
        fingerprint, target_count, grid_cell_count = _prepare_targets(
            connection,
            config.category_key,
            context.grid_version,
            provider_context=provider_context,
        )
        rows = connection.execute(statement, parameters)
        values: list[tuple[str, float]] = []
        spatial_match_count = 0
        for cell_id, raw_value, match_count in rows:
            value = float(cast(Any, raw_value))
            if not math.isfinite(value) or value < 0 or value > 1.000000000001:
                raise MetricProviderError(
                    f"accessibility value outside 0..1: {cell_id}={value}"
                )
            values.append((str(cell_id), min(value, 1.0)))
            spatial_match_count += int(cast(Any, match_count))
    return MetricCalculation(
        input_fingerprint=fingerprint,
        values=tuple(values),
        diagnostics={
            "category_key": config.category_key,
            "half_distance_m": config.half_distance_m,
            "cutoff_distance_m": config.half_distance_m * config.cutoff_multiplier,
            "target_count": target_count,
            "grid_cell_count": grid_cell_count,
            "spatial_match_count": spatial_match_count,
            **diagnostics,
        },
        calculation_duration_seconds=monotonic() - started,
    )


class CatalogPrimaryAccessibilityProvider:
    def calculate(self, context: MetricProviderContext) -> MetricCalculation:
        try:
            config = CatalogPrimaryAccessibilityConfig.model_validate(
                context.definition.provider_config
            )
        except ValueError as exc:
            raise MetricProviderError(
                f"invalid primary-accessibility config: {exc}"
            ) from exc
        return _accessibility_calculation(
            context,
            config,
            _PRIMARY_ACCESSIBILITY_SQL,
            _accessibility_parameters(config, context.grid_version),
            {
                "model": "nearest_primary_bounded_bonus_v2",
                "extra_bonus_cap": config.extra_bonus_cap,
                "extra_saturation": config.extra_saturation,
            },
        )


class CatalogParkAccessibilityProvider:
    def calculate(self, context: MetricProviderContext) -> MetricCalculation:
        try:
            config = CatalogParkAccessibilityConfig.model_validate(
                context.definition.provider_config
            )
        except ValueError as exc:
            raise MetricProviderError(f"invalid park-accessibility config: {exc}") from exc
        parameters = _accessibility_parameters(config, context.grid_version)
        parameters.update(
            {
                "area_reference_m2": config.area_reference_m2,
                "minimum_size_quality": config.minimum_size_quality,
            }
        )
        return _accessibility_calculation(
            context,
            config,
            _PARK_ACCESSIBILITY_SQL,
            parameters,
            {
                "model": "park_size_proximity_v2",
                "area_reference_m2": config.area_reference_m2,
                "minimum_size_quality": config.minimum_size_quality,
                "extra_bonus_cap": config.extra_bonus_cap,
                "extra_saturation": config.extra_saturation,
            },
        )


class CatalogWaterAccessibilityProvider:
    def calculate(self, context: MetricProviderContext) -> MetricCalculation:
        try:
            config = CatalogWaterAccessibilityConfig.model_validate(
                context.definition.provider_config
            )
        except ValueError as exc:
            raise MetricProviderError(f"invalid water-accessibility config: {exc}") from exc
        parameters = _accessibility_parameters(config, context.grid_version)
        parameters.update(
            {
                "area_reference_m2": config.area_reference_m2,
                "minimum_size_quality": config.minimum_size_quality,
                "line_quality": config.line_quality,
            }
        )
        return _accessibility_calculation(
            context,
            config,
            _WATER_ACCESSIBILITY_SQL,
            parameters,
            {
                "model": "water_nearest_geometry_v2",
                "area_reference_m2": config.area_reference_m2,
                "minimum_size_quality": config.minimum_size_quality,
                "line_quality": config.line_quality,
                "segmentation_bonus": False,
            },
        )
