import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.analytics.metrics.contracts import MetricDefinition
from app.analytics.metrics.publisher import values_checksum
from app.analytics.metrics.registry import MetricRegistry, MetricRegistryError


def metric_payload(key: str = "test.synthetic.value") -> dict[str, object]:
    return {
        "key": key,
        "definition_version": "1",
        "label": "Synthetic value",
        "description": "Test-only deterministic metric",
        "group": "test",
        "unit": "index",
        "value_semantics": "index",
        "preferred_direction": "context_only",
        "provider_key": "test.synthetic",
        "calculation_version": "1",
        "provider_config": {"seed": 7},
        "source_dependencies": ["analytics.analysis_cells"],
        "enabled": True,
    }


def test_definition_is_strict_and_checksum_is_deterministic() -> None:
    first = MetricDefinition.model_validate(metric_payload())
    second = MetricDefinition.model_validate(metric_payload())
    assert first.checksum() == second.checksum()
    assert len(first.checksum()) == 64

    invalid = metric_payload("Bad Key")
    with pytest.raises(ValidationError):
        MetricDefinition.model_validate(invalid)

    extra = metric_payload()
    extra["unknown"] = True
    with pytest.raises(ValidationError):
        MetricDefinition.model_validate(extra)


def test_registry_orders_definitions_and_rejects_duplicate_keys() -> None:
    last = MetricDefinition.model_validate(metric_payload("test.zeta.value"))
    first = MetricDefinition.model_validate(metric_payload("test.alpha.value"))
    registry = MetricRegistry([last, first])
    assert [item.key for item in registry.list()] == ["test.alpha.value", "test.zeta.value"]
    assert len(registry.checksum()) == 64

    with pytest.raises(MetricRegistryError, match="duplicate metric keys"):
        MetricRegistry([first, first])


def test_registry_file_validation_and_empty_production_registry(tmp_path: Path) -> None:
    empty = tmp_path / "empty.json"
    empty.write_text('{"metrics": []}', encoding="utf-8")
    assert MetricRegistry.load(empty).list() == ()

    duplicate = tmp_path / "duplicate.json"
    duplicate.write_text(
        json.dumps({"metrics": [metric_payload(), metric_payload()]}), encoding="utf-8"
    )
    with pytest.raises(MetricRegistryError, match="duplicate metric keys"):
        MetricRegistry.load(duplicate)


def test_value_checksum_is_order_independent_and_float_exact() -> None:
    first = values_checksum([("cell-b", -1.25), ("cell-a", 0.0)])
    assert first == values_checksum([("cell-a", 0.0), ("cell-b", -1.25)])
    assert first != values_checksum([("cell-a", -0.0), ("cell-b", -1.25)])
