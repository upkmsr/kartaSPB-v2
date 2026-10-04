from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy import Engine

from app.analytics.metrics.contracts import MetricDefinition


@dataclass(frozen=True)
class MetricProviderContext:
    engine: Engine
    definition: MetricDefinition
    grid_version: str


class MetricProvider(Protocol):
    def calculate(self, context: MetricProviderContext) -> Iterable[tuple[str, float]]: ...


class MetricProviderRegistry:
    def __init__(self, providers: dict[str, MetricProvider] | None = None) -> None:
        self._providers = providers or {}

    def get(self, key: str) -> MetricProvider | None:
        return self._providers.get(key)
