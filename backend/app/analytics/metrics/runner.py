import math
from time import monotonic
from typing import Any

from sqlalchemy import Engine

from app.analytics.metrics.contracts import MetricDefinition, MetricValueSemantics
from app.analytics.metrics.providers import (
    MetricCalculation,
    MetricProvider,
    MetricProviderContext,
)
from app.analytics.metrics.publisher import publish_metric


class MetricSanityError(RuntimeError):
    """Raised when calculated raw values violate metric semantics."""


def validate_calculation(
    definition: MetricDefinition, calculation: MetricCalculation
) -> None:
    values = [raw_value for _, raw_value in calculation.values]
    expected_count = calculation.diagnostics.get("grid_cell_count")
    if not values or (expected_count is not None and len(values) != expected_count):
        raise MetricSanityError(
            f"calculation is not complete: values={len(values)}, expected={expected_count}"
        )
    if any(not math.isfinite(value) or value < 0 for value in values):
        raise MetricSanityError("metric values must be finite and non-negative")
    minimum = min(values)
    maximum = max(values)
    if definition.value_semantics == MetricValueSemantics.DISTANCE_M:
        if minimum < 0 or maximum <= minimum:
            raise MetricSanityError("distance metric must have max > min >= 0")
    elif definition.value_semantics == MetricValueSemantics.COUNT:
        if maximum <= 0 or any(not value.is_integer() for value in values):
            raise MetricSanityError(
                "count metric must be integral, non-negative, and have max > 0"
            )
    elif definition.value_semantics == MetricValueSemantics.INDEX:
        if minimum < 0 or maximum <= minimum or maximum <= 0:
            raise MetricSanityError("index metric must have max > min >= 0")
    else:
        raise MetricSanityError(
            f"unsupported F8 value semantics: {definition.value_semantics.value}"
        )


def run_metric(
    engine: Engine,
    definition: MetricDefinition,
    provider: MetricProvider,
    grid_version: str,
) -> dict[str, Any]:
    calculation = provider.calculate(
        MetricProviderContext(
            engine=engine, definition=definition, grid_version=grid_version
        )
    )
    validate_calculation(definition, calculation)
    publication_started = monotonic()
    publication = publish_metric(
        engine,
        definition,
        grid_version,
        calculation.input_fingerprint,
        calculation.values,
    )
    report = publication.to_dict()
    report.update(
        {
            "input_fingerprint": calculation.input_fingerprint,
            "calculation_duration_seconds": calculation.calculation_duration_seconds,
            "publication_duration_seconds": monotonic() - publication_started,
            "diagnostics": calculation.diagnostics,
        }
    )
    return report
