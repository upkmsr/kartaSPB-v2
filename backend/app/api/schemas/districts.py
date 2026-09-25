from uuid import UUID

from pydantic import BaseModel


class DistrictSummary(BaseModel):
    id: UUID
    name: str
    slug: str
    bbox: tuple[float, float, float, float]
    display_order: int


class DistrictList(BaseModel):
    districts: list[DistrictSummary]
