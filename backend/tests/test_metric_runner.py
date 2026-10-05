import math

import pytest

from app.analytics.metrics.contracts import MetricDefinition
from app.analytics.metrics.providers import MetricCalculation
from app.analytics.metrics.runner import MetricSanityError, validate_calculation


def definition(semantics: str) -> MetricDefinition:
    return MetricDefinition.model_validate(
        {
            "key": f"test.synthetic.{semantics}",
            "definition_version": "1",
            "label": "Synthetic",
            "description": "Fixture",
            "group": "test",
            "unit": "m" if semantics == "distance_m" else "count",
            "value_semantics": semantics,
            "preferred_direction": "lower_better",
            "provider_key": "test.synthetic",
            "calculation_version": "1",
        }
    )


def calculation(values: tuple[float, ...], expected: int | None = None) -> MetricCalculation:
    diagnostics = {} if expected is None else {"grid_cell_count": expected}
    return MetricCalculation(
        input_fingerprint="a" * 64,
        values=tuple((f"cell-{index}", value) for index, value in enumerate(values)),
        diagnostics=diagnostics,
        calculation_duration_seconds=0.1,
    )


def test_distance_and_count_sanity_accept_valid_values() -> None:
    validate_calculation(definition("distance_m"), calculation((0.0, 10.5), 2))
    validate_calculation(definition("count"), calculation((0.0, 2.0), 2))


@pytest.mark.parametrize(
    ("semantics", "values", "message"),
    [
        ("distance_m", (), "not complete"),
        ("distance_m", (0.0,), "max > min"),
        ("distance_m", (-1.0, 1.0), "finite and non-negative"),
        ("distance_m", (0.0, math.inf), "finite and non-negative"),
        ("count", (0.0, 1.5), "integral"),
        ("count", (0.0, 0.0), "max > 0"),
    ],
)
def test_metric_sanity_fails_closed(
    semantics: str, values: tuple[float, ...], message: str
) -> None:
    with pytest.raises(MetricSanityError, match=message):
        validate_calculation(definition(semantics), calculation(values))


def test_metric_sanity_requires_complete_grid() -> None:
    with pytest.raises(MetricSanityError, match="values=2, expected=3"):
        validate_calculation(definition("count"), calculation((0.0, 1.0), 3))
