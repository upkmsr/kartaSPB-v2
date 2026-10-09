import json
import os
import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

from app.analytics.metrics.registry import MetricRegistry
from app.analytics.scoring.registry import NormalizationRegistry


class ScenarioRegistryError(RuntimeError):
    """Raised when the user-facing scenario dimension contract is invalid."""


class ScenarioDimension(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    key: str
    label: str
    group: str
    group_label: str
    metric_key: str
    display_order: int
    enabled: bool = True

    @field_validator("key", "group")
    @classmethod
    def stable_key(cls, value: str) -> str:
        if re.fullmatch(r"[a-z][a-z0-9_]*", value) is None:
            raise ValueError("must be a stable lowercase key")
        return value

    @field_validator("label", "group_label", "metric_key")
    @classmethod
    def non_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value


class _ScenarioDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dimensions: list[ScenarioDimension]


def default_scenario_path() -> Path:
    project_root = os.getenv("PROJECT_ROOT")
    root = Path(project_root) if project_root else Path(__file__).resolve().parents[3]
    return root / "config" / "analytics" / "scenarios" / "dimensions.json"


class ScenarioRegistry:
    def __init__(
        self,
        dimensions: Iterable[ScenarioDimension],
        metric_registry: MetricRegistry | None = None,
        normalization_registry: NormalizationRegistry | None = None,
    ) -> None:
        ordered = sorted(dimensions, key=lambda item: (item.display_order, item.key))
        keys = [item.key for item in ordered]
        orders = [item.display_order for item in ordered]
        metric_keys = [item.metric_key for item in ordered]
        if len(keys) != len(set(keys)):
            raise ScenarioRegistryError("duplicate scenario dimension keys")
        if len(orders) != len(set(orders)):
            raise ScenarioRegistryError("duplicate scenario dimension display orders")
        if len(metric_keys) != len(set(metric_keys)):
            raise ScenarioRegistryError("duplicate scenario dimension metrics")
        metrics = metric_registry or MetricRegistry.load()
        normalizations = normalization_registry or NormalizationRegistry.load(
            metric_registry=metrics
        )
        for item in ordered:
            metric = metrics.get(item.metric_key)
            normalization = normalizations.get(item.metric_key)
            if metric is None or normalization is None:
                raise ScenarioRegistryError(
                    f"scenario dimension is not backed by an enabled metric and normalization: "
                    f"{item.key}"
                )
            if metric.value_semantics.value != "index":
                raise ScenarioRegistryError(
                    f"scenario dimension must use an index metric: {item.key}"
                )
        self._dimensions = tuple(ordered)

    @classmethod
    def load(cls, path: Path | None = None) -> "ScenarioRegistry":
        target = path or default_scenario_path()
        try:
            payload: Any = json.loads(target.read_text(encoding="utf-8"))
            document = _ScenarioDocument.model_validate(payload)
        except (OSError, json.JSONDecodeError, ValidationError) as exc:
            raise ScenarioRegistryError(f"invalid scenario registry {target}: {exc}") from exc
        return cls(document.dimensions)

    def list(self, *, enabled_only: bool = True) -> tuple[ScenarioDimension, ...]:
        if not enabled_only:
            return self._dimensions
        return tuple(item for item in self._dimensions if item.enabled)
