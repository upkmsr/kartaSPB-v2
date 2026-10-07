import hashlib
import json
import math
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, field_validator

from app.analytics.metrics.contracts import METRIC_KEY_PATTERN, MetricDirection


class NormalizationMethod(StrEnum):
    PIECEWISE_LINEAR = "piecewise_linear"


class NormalizationPoint(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    raw_value: float
    score: float

    @field_validator("raw_value", "score")
    @classmethod
    def require_finite(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("normalization point values must be finite")
        return value

    @field_validator("score")
    @classmethod
    def score_in_range(cls, value: float) -> float:
        if not 0 <= value <= 100:
            raise ValueError("score must be between 0 and 100")
        return value


class NormalizationDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    metric_key: str
    normalization_version: str
    label: str
    method: NormalizationMethod
    points: tuple[NormalizationPoint, ...]
    enabled: bool = True
    notes: str

    @field_validator("metric_key")
    @classmethod
    def valid_metric_key(cls, value: str) -> str:
        if not METRIC_KEY_PATTERN.fullmatch(value):
            raise ValueError("metric_key must be a stable lowercase dotted key")
        return value

    @field_validator("normalization_version", "label", "notes")
    @classmethod
    def reject_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value

    @field_validator("points", mode="before")
    @classmethod
    def expand_point_pairs(cls, value: object) -> object:
        if not isinstance(value, list):
            return value
        return [
            {"raw_value": point[0], "score": point[1]}
            if isinstance(point, list) and len(point) == 2
            else point
            for point in value
        ]

    @field_validator("points")
    @classmethod
    def valid_points(
        cls, value: tuple[NormalizationPoint, ...]
    ) -> tuple[NormalizationPoint, ...]:
        if len(value) < 2:
            raise ValueError("at least two normalization points are required")
        raw_values = [point.raw_value for point in value]
        if any(right <= left for left, right in zip(raw_values, raw_values[1:], strict=False)):
            raise ValueError("raw x-values must be strictly increasing")
        return value

    def validate_direction(self, direction: MetricDirection) -> None:
        scores = [point.score for point in self.points]
        if direction == MetricDirection.LOWER_BETTER and any(
            right > left for left, right in zip(scores, scores[1:], strict=False)
        ):
            raise ValueError(f"{self.metric_key}: lower_better curve must not increase")
        if direction == MetricDirection.HIGHER_BETTER and any(
            right < left for left, right in zip(scores, scores[1:], strict=False)
        ):
            raise ValueError(f"{self.metric_key}: higher_better curve must not decrease")
        if direction not in {MetricDirection.LOWER_BETTER, MetricDirection.HIGHER_BETTER}:
            raise ValueError(f"{self.metric_key}: unsupported scoring direction {direction.value}")

    def normalize(self, raw_value: float) -> float:
        if not math.isfinite(raw_value):
            raise ValueError("raw value must be finite")
        if raw_value <= self.points[0].raw_value:
            return self.points[0].score
        if raw_value >= self.points[-1].raw_value:
            return self.points[-1].score
        for left, right in zip(self.points, self.points[1:], strict=False):
            if raw_value <= right.raw_value:
                fraction = (raw_value - left.raw_value) / (right.raw_value - left.raw_value)
                return left.score + fraction * (right.score - left.score)
        raise AssertionError("normalization point interval was not found")

    def snapshot(self) -> dict[str, object]:
        return self.model_dump(mode="json")

    def canonical_json(self) -> str:
        return json.dumps(
            self.snapshot(), sort_keys=True, separators=(",", ":"), ensure_ascii=False
        )

    def checksum(self) -> str:
        return hashlib.sha256(self.canonical_json().encode()).hexdigest()
