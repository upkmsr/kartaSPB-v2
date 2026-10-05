import pytest

from app.analytics.metrics.__main__ import execute
from app.analytics.metrics.contracts import MetricDefinition
from app.analytics.metrics.providers import MetricProviderRegistry
from app.analytics.metrics.registry import MetricRegistry, MetricRegistryError


def definition() -> MetricDefinition:
    return MetricDefinition.model_validate(
        {
            "key": "test.synthetic.value",
            "definition_version": "1",
            "label": "Synthetic",
            "description": "Fixture",
            "group": "test",
            "unit": "index",
            "value_semantics": "index",
            "preferred_direction": "context_only",
            "provider_key": "test.synthetic",
            "calculation_version": "1",
        }
    )


def test_validate_and_list_commands_are_json_ready() -> None:
    registry = MetricRegistry([definition()])
    validation = execute(["validate"], registry=registry)
    assert validation["status"] == "valid"
    assert validation["metric_count"] == 1
    assert len(str(validation["registry_checksum"])) == 64

    listed = execute(["list"], registry=registry)
    assert listed["metrics"][0]["key"] == "test.synthetic.value"  # type: ignore[index]


def test_run_fails_closed_without_registered_definition_or_provider() -> None:
    with pytest.raises(MetricRegistryError, match="unknown or disabled metric"):
        execute(
            [
                "run",
                "--metric",
                "test.synthetic.value",
            ],
            registry=MetricRegistry([]),
        )

    with pytest.raises(MetricRegistryError, match="provider is not registered"):
        execute(
            [
                "run",
                "--metric",
                "test.synthetic.value",
            ],
            registry=MetricRegistry([definition()]),
            providers=MetricProviderRegistry(),
        )
