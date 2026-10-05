from dataclasses import dataclass
from typing import Any, Protocol

from sqlalchemy import Engine

from app.analytics.metrics.contracts import MetricDefinition


@dataclass(frozen=True)
class MetricProviderContext:
    engine: Engine
    definition: MetricDefinition
    grid_version: str


@dataclass(frozen=True)
class MetricCalculation:
    input_fingerprint: str
    values: tuple[tuple[str, float], ...]
    diagnostics: dict[str, Any]
    calculation_duration_seconds: float


class MetricProvider(Protocol):
    def calculate(self, context: MetricProviderContext) -> MetricCalculation: ...


class MetricProviderRegistry:
    def __init__(self, providers: dict[str, MetricProvider] | None = None) -> None:
        self._providers = providers or {}

    def get(self, key: str) -> MetricProvider | None:
        return self._providers.get(key)

    @classmethod
    def production(cls) -> "MetricProviderRegistry":
        from app.analytics.metrics.catalog import (
            CatalogCountWithinRadiusProvider,
            CatalogNearestDistanceProvider,
        )

        return cls(
            {
                "catalog.nearest_distance": CatalogNearestDistanceProvider(),
                "catalog.count_within_radius": CatalogCountWithinRadiusProvider(),
            }
        )
