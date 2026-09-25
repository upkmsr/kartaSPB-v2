from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel


class GeoJSONGeometry(BaseModel):
    type: str
    coordinates: list[Any]


class MapFeatureProperties(BaseModel):
    canonical_id: UUID
    name: str | None
    categories: list[str]
    object_kind: str


class GeoJSONFeature(BaseModel):
    type: Literal["Feature"] = "Feature"
    id: UUID
    geometry: GeoJSONGeometry
    properties: MapFeatureProperties


class GeoJSONFeatureCollection(BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[GeoJSONFeature]


class SourceSummary(BaseModel):
    provider: str
    object_type: str
    object_id: str
    source_version: str | None
    geometry_quality: str


class ObjectDetail(BaseModel):
    id: UUID
    name: str | None
    categories: list[str]
    object_kind: str
    geometry_type: str
    properties: dict[str, Any]
    sources: list[SourceSummary]


class ErrorDetail(BaseModel):
    code: str
    message: str
    requested_limit: int | None = None
    suggestion: str | None = None
    unknown_categories: list[str] | None = None


class ErrorResponse(BaseModel):
    detail: ErrorDetail
