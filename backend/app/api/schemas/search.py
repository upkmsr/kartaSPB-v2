from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from app.api.schemas.map import GeoJSONGeometry


class SearchResult(BaseModel):
    id: UUID
    name: str
    categories: list[str]
    object_kind: str
    geometry_type: str
    representative_point: GeoJSONGeometry
    bbox: tuple[float, float, float, float]


class SearchResultList(BaseModel):
    type: Literal["SearchResults"] = "SearchResults"
    results: list[SearchResult]
