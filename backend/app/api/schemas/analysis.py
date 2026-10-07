from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class AnalysisGridDistrictCount(BaseModel):
    district_id: UUID
    cell_count: int


class AnalysisGridMeta(BaseModel):
    grid_version: str
    cell_size_m: int
    metric_srid: int
    display_srid: int
    cell_count: int
    district_count: int
    district_cell_counts: list[AnalysisGridDistrictCount]
    bbox: list[float] | None


class MetricDefinitionPublic(BaseModel):
    key: str
    definition_version: str
    label: str
    description: str
    group: str
    unit: str
    value_semantics: str
    preferred_direction: str
    calculation_version: str
    enabled: bool


class CurrentMetricRunPublic(BaseModel):
    run_id: UUID
    metric_key: str
    definition_version: str
    calculation_version: str
    grid_version: str
    cell_count: int
    min_value: float
    max_value: float
    mean_value: float
    values_checksum: str
    created_at: datetime


class NormalizationPointPublic(BaseModel):
    raw_value: float
    score: float


class NormalizationDefinitionPublic(BaseModel):
    metric_key: str
    normalization_version: str
    label: str
    method: str
    points: list[NormalizationPointPublic]
    checksum: str


class ScoreEvaluationRequest(BaseModel):
    grid_version: str | None = None
    weights: dict[str, float]
    limit: int = Field(default=20, ge=1, le=100)


class ScoredCellPublic(BaseModel):
    cell_id: str
    score: float
    district_id: UUID


class ScoreEvaluationPublic(BaseModel):
    grid_version: str
    weights: dict[str, float]
    scoring_signature: str
    cell_count: int
    min: float
    max: float
    mean: float
    top_cells: list[ScoredCellPublic]
