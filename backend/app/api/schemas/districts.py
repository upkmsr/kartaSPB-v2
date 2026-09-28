from typing import Any, Literal
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


class DistrictGeometry(BaseModel):
    type: Literal["Polygon", "MultiPolygon"]
    coordinates: list[Any]


class DistrictGeometryProperties(BaseModel):
    id: UUID
    name: str
    slug: str


class DistrictGeometryFeature(BaseModel):
    type: Literal["Feature"] = "Feature"
    id: UUID
    properties: DistrictGeometryProperties
    geometry: DistrictGeometry


class DistrictGeometryFeatureCollection(BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[DistrictGeometryFeature]
