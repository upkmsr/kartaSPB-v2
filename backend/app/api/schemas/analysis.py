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
