import hashlib
import json
import os
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError

from app.analytics.metrics.registry import MetricRegistry
from app.analytics.scoring.contracts import NormalizationDefinition


class NormalizationRegistryError(RuntimeError):
    """Raised when normalization configuration violates the F9 contract."""


class _RegistryDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")
    normalizations: list[NormalizationDefinition]


def default_registry_path() -> Path:
    project_root = os.getenv("PROJECT_ROOT")
    root = Path(project_root) if project_root else Path(__file__).resolve().parents[4]
    return root / "config" / "analytics" / "scoring" / "normalizations.json"


class NormalizationRegistry:
    def __init__(
        self,
        definitions: Iterable[NormalizationDefinition],
        metric_registry: MetricRegistry,
    ) -> None:
        ordered = sorted(definitions, key=lambda definition: definition.metric_key)
        keys = [definition.metric_key for definition in ordered]
        if len(keys) != len(set(keys)):
            raise NormalizationRegistryError("duplicate normalization metric keys")
        for definition in ordered:
            metric = metric_registry.get(definition.metric_key)
            if metric is None:
                raise NormalizationRegistryError(
                    f"unknown or disabled metric: {definition.metric_key}"
                )
            try:
                definition.validate_direction(metric.preferred_direction)
            except ValueError as exc:
                raise NormalizationRegistryError(str(exc)) from exc
        self._definitions = tuple(ordered)
        self._by_key = {definition.metric_key: definition for definition in ordered}

    @classmethod
    def load(
        cls,
        path: Path | None = None,
        metric_registry: MetricRegistry | None = None,
    ) -> "NormalizationRegistry":
        target = path or default_registry_path()
        try:
            payload: Any = json.loads(target.read_text(encoding="utf-8"))
            document = _RegistryDocument.model_validate(payload)
        except (OSError, json.JSONDecodeError, ValidationError) as exc:
            raise NormalizationRegistryError(
                f"invalid normalization registry {target}: {exc}"
            ) from exc
        return cls(document.normalizations, metric_registry or MetricRegistry.load())

    def list(self, *, enabled_only: bool = True) -> tuple[NormalizationDefinition, ...]:
        if not enabled_only:
            return self._definitions
        return tuple(item for item in self._definitions if item.enabled)

    def get(self, metric_key: str) -> NormalizationDefinition | None:
        definition = self._by_key.get(metric_key)
        return definition if definition is not None and definition.enabled else None

    def checksum(self) -> str:
        payload = [definition.snapshot() for definition in self._definitions]
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(canonical.encode()).hexdigest()
