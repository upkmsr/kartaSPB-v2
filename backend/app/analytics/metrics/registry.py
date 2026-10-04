import hashlib
import json
import os
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError

from app.analytics.metrics.contracts import MetricDefinition


class MetricRegistryError(RuntimeError):
    """Raised when metric registry configuration violates the F7 contract."""


class _RegistryDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")
    metrics: list[MetricDefinition]


def default_registry_path() -> Path:
    project_root = os.getenv("PROJECT_ROOT")
    root = Path(project_root) if project_root else Path(__file__).resolve().parents[4]
    return root / "config" / "analytics" / "metrics" / "registry.json"


class MetricRegistry:
    def __init__(self, definitions: Iterable[MetricDefinition]) -> None:
        ordered = sorted(definitions, key=lambda definition: definition.key)
        keys = [definition.key for definition in ordered]
        if len(keys) != len(set(keys)):
            duplicates = sorted({key for key in keys if keys.count(key) > 1})
            raise MetricRegistryError(f"duplicate metric keys: {', '.join(duplicates)}")
        self._definitions = tuple(ordered)
        self._by_key = {definition.key: definition for definition in ordered}

    @classmethod
    def load(cls, path: Path | None = None) -> "MetricRegistry":
        target = path or default_registry_path()
        try:
            payload: Any = json.loads(target.read_text(encoding="utf-8"))
            document = _RegistryDocument.model_validate(payload)
        except (OSError, json.JSONDecodeError, ValidationError) as exc:
            raise MetricRegistryError(f"invalid metric registry {target}: {exc}") from exc
        return cls(document.metrics)

    def list(self, *, enabled_only: bool = True) -> tuple[MetricDefinition, ...]:
        if not enabled_only:
            return self._definitions
        return tuple(item for item in self._definitions if item.enabled)

    def get(self, key: str) -> MetricDefinition | None:
        definition = self._by_key.get(key)
        return definition if definition is not None and definition.enabled else None

    def checksum(self) -> str:
        payload = [definition.snapshot() for definition in self._definitions]
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(canonical.encode()).hexdigest()
