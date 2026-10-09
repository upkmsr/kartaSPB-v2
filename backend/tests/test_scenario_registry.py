import json
from pathlib import Path

import pytest

from app.analytics.scenarios import (
    ScenarioRegistry,
    ScenarioRegistryError,
    default_scenario_path,
)


def test_production_scenario_registry_exposes_exactly_eight_smooth_dimensions() -> None:
    dimensions = ScenarioRegistry.load().list()
    assert len(dimensions) == 8
    assert [item.display_order for item in dimensions] == list(range(10, 81, 10))
    assert all(item.metric_key.endswith(".accessibility_index") for item in dimensions)
    assert {item.group for item in dimensions} == {
        "education",
        "transport",
        "healthcare",
        "nature",
    }


def test_scenario_registry_rejects_duplicate_keys(tmp_path: Path) -> None:
    source = json.loads(
        default_scenario_path().read_text(encoding="utf-8")
    )
    source["dimensions"].append(source["dimensions"][0])
    target = tmp_path / "dimensions.json"
    target.write_text(json.dumps(source), encoding="utf-8")
    with pytest.raises(ScenarioRegistryError, match="duplicate"):
        ScenarioRegistry.load(target)
