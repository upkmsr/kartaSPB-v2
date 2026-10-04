import hashlib
import json
import re
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

METRIC_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*){2,}$")


class MetricValueSemantics(StrEnum):
    DISTANCE_M = "distance_m"
    COUNT = "count"
    AREA_M2 = "area_m2"
    RATIO = "ratio"
    PERCENT = "percent"
    DURATION_MIN = "duration_min"
    INDEX = "index"
    SCORE = "score"
    OTHER = "other"


class MetricDirection(StrEnum):
    LOWER_BETTER = "lower_better"
    HIGHER_BETTER = "higher_better"
    TARGET_RANGE = "target_range"
    CONTEXT_ONLY = "context_only"


class MetricDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    key: str
    definition_version: str
    label: str
    description: str
    group: str
    unit: str
    value_semantics: MetricValueSemantics
    preferred_direction: MetricDirection
    provider_key: str
    calculation_version: str
    provider_config: dict[str, Any] = Field(default_factory=dict)
    source_dependencies: tuple[str, ...] = ()
    enabled: bool = True

    @field_validator(
        "definition_version",
        "label",
        "description",
        "group",
        "unit",
        "provider_key",
        "calculation_version",
    )
    @classmethod
    def reject_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value

    @field_validator("key")
    @classmethod
    def validate_key(cls, value: str) -> str:
        if not METRIC_KEY_PATTERN.fullmatch(value):
            raise ValueError("must be a stable lowercase dotted key with at least 3 parts")
        return value

    @field_validator("source_dependencies")
    @classmethod
    def reject_duplicate_dependencies(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(not item.strip() for item in value):
            raise ValueError("source dependencies must not be blank")
        if len(set(value)) != len(value):
            raise ValueError("source dependencies must be unique")
        return value

    def snapshot(self) -> dict[str, Any]:
        return self.model_dump(mode="json")

    def canonical_json(self) -> str:
        return json.dumps(
            self.snapshot(), sort_keys=True, separators=(",", ":"), ensure_ascii=False
        )

    def checksum(self) -> str:
        return hashlib.sha256(self.canonical_json().encode()).hexdigest()
