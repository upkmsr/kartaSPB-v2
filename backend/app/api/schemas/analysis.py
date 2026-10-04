from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


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
