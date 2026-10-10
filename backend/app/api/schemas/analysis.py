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


class ScoreDistributionRequest(BaseModel):
    grid_version: str | None = None
    weights: dict[str, float]
    district_ids: list[UUID] = Field(min_length=1, max_length=18)


class ScoreDistributionPublic(BaseModel):
    grid_version: str
    scoring_signature: str
    cell_count: int
    p10: float
    p25: float
    p50: float
    p75: float
    p90: float


class ScenarioDimensionPublic(BaseModel):
    key: str
    label: str
    group: str
    group_label: str
    metric_key: str
    display_order: int


class HeatmapPrepareRequest(BaseModel):
    grid_version: str | None = None
    weights: dict[str, float]


class HeatmapPreparePublic(BaseModel):
    grid_version: str
    weights: dict[str, float]
    scoring_signature: str
    spec: str
    cell_count: int
    min: float
    max: float
    mean: float
    tile_url_template: str
    delivery_version: str


class ScenarioExplainRequest(BaseModel):
    cell_id: str = Field(min_length=1, max_length=160)
    spec: str = Field(min_length=1, max_length=8192)


class ScenarioExplanationTargetPublic(BaseModel):
    object_id: UUID
    name: str | None
    geometry_type: str
    distance_m: float
    area_m2: float | None


class ScenarioExplanationFactorPublic(BaseModel):
    metric_key: str
    label: str
    weight: float
    individual_score: float
    contribution: float
    target: ScenarioExplanationTargetPublic | None


class ScenarioExplanationPublic(BaseModel):
    grid_version: str
    cell_id: str
    scoring_signature: str
    score: float
    factors: list[ScenarioExplanationFactorPublic]
