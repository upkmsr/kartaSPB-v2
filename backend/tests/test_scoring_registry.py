import math

import pytest
from pydantic import ValidationError

from app.analytics.metrics.contracts import MetricDefinition
from app.analytics.metrics.registry import MetricRegistry
from app.analytics.scoring.contracts import NormalizationDefinition
from app.analytics.scoring.engine import ScoringError, validate_weights
from app.analytics.scoring.registry import NormalizationRegistry, NormalizationRegistryError


def metric(key: str, direction: str = "lower_better") -> MetricDefinition:
    return MetricDefinition.model_validate(
        {
            "key": key,
            "definition_version": "1",
            "label": "Fixture",
            "description": "Fixture",
            "group": "test",
            "unit": "index",
            "value_semantics": "index",
            "preferred_direction": direction,
            "provider_key": "test.synthetic",
            "calculation_version": "1",
        }
    )


def normalization(
    key: str = "test.synthetic.value",
    points: list[list[float]] | None = None,
    *,
    version: str = "1",
) -> NormalizationDefinition:
    return NormalizationDefinition.model_validate(
        {
            "metric_key": key,
            "normalization_version": version,
            "label": "Fixture",
            "method": "piecewise_linear",
            "points": points or [[0, 100], [10, 50], [20, 0]],
            "enabled": True,
            "notes": "Fixture only",
        }
    )


def test_production_normalization_registry_has_existing_and_smooth_profiles() -> None:
    registry = NormalizationRegistry.load()
    assert len(registry.list()) == 20
    assert len(
        [item for item in registry.list() if item.metric_key.endswith(".accessibility_index")]
    ) == 8
    assert len(registry.checksum()) == 64
    assert {definition.normalization_version for definition in registry.list()} == {"1"}
    assert {definition.method.value for definition in registry.list()} == {
        "piecewise_linear"
    }


def test_piecewise_linear_exact_anchors_interpolation_and_clamps() -> None:
    definition = normalization()
    assert definition.normalize(-5) == 100
    assert definition.normalize(0) == 100
    assert definition.normalize(5) == 75
    assert definition.normalize(10) == 50
    assert definition.normalize(15) == 25
    assert definition.normalize(20) == 0
    assert definition.normalize(25) == 0


@pytest.mark.parametrize(
    ("points", "message"),
    [
        ([[0, 100]], "at least two"),
        ([[0, 100], [0, 50]], "strictly increasing"),
        ([[10, 100], [0, 50]], "strictly increasing"),
        ([[0, -1], [10, 50]], "between 0 and 100"),
        ([[0, 101], [10, 50]], "between 0 and 100"),
    ],
)
def test_invalid_points_are_rejected(points: list[list[float]], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        normalization(points=points)


def test_non_finite_raw_value_is_rejected() -> None:
    with pytest.raises(ValueError, match="finite"):
        normalization().normalize(math.nan)


def test_direction_validation_rejects_inconsistent_curves() -> None:
    key = "test.synthetic.value"
    with pytest.raises(NormalizationRegistryError, match="must not increase"):
        NormalizationRegistry(
            [normalization(key, [[0, 0], [10, 100]])],
            MetricRegistry([metric(key, "lower_better")]),
        )
    with pytest.raises(NormalizationRegistryError, match="must not decrease"):
        NormalizationRegistry(
            [normalization(key, [[0, 100], [10, 0]])],
            MetricRegistry([metric(key, "higher_better")]),
        )


def test_definition_and_registry_checksums_are_deterministic_and_versioned() -> None:
    key = "test.synthetic.value"
    metrics = MetricRegistry([metric(key)])
    first = normalization(key)
    assert first.checksum() == normalization(key).checksum()
    changed = normalization(key, version="2")
    assert first.checksum() != changed.checksum()
    assert NormalizationRegistry([first], metrics).checksum() != NormalizationRegistry(
        [changed], metrics
    ).checksum()


def test_weight_contract_accepts_only_explicit_finite_range_and_positive_selection() -> None:
    key = "test.synthetic.value"
    registry = NormalizationRegistry([normalization(key)], MetricRegistry([metric(key)]))
    assert validate_weights({key: 50}, registry) == {key: 50.0}
    with pytest.raises(ScoringError, match="positive"):
        validate_weights({}, registry)
    with pytest.raises(ScoringError, match="positive"):
        validate_weights({key: 0}, registry)
    for weight in (-1, 101):
        with pytest.raises(ScoringError, match="between 0 and 100"):
            validate_weights({key: weight}, registry)
    for weight in (math.nan, math.inf):
        with pytest.raises(ScoringError, match="finite"):
            validate_weights({key: weight}, registry)
    with pytest.raises(ScoringError, match="unknown"):
        validate_weights({"unknown.metric.value": 50}, registry)
