import json
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import Engine, text

from app.api.map_validation import BoundingBox


class UnknownCategoriesError(ValueError):
    def __init__(self, categories: list[str]) -> None:
        self.categories = categories
        super().__init__(f"Unknown or disabled categories: {', '.join(categories)}")


class FeatureLimitExceededError(ValueError):
    def __init__(self, requested_limit: int) -> None:
        self.requested_limit = requested_limit
        super().__init__(f"Feature limit {requested_limit} exceeded")


@dataclass(frozen=True)
class MapFeatureData:
    id: UUID
    name: str | None
    object_kind: str
    geometry: dict[str, Any]
    categories: list[str]


@dataclass(frozen=True)
class SourceSummaryData:
    provider: str
    object_type: str
    object_id: str
    source_version: str | None
    geometry_quality: str


@dataclass(frozen=True)
class ObjectDetailData:
    id: UUID
    name: str | None
    categories: list[str]
    object_kind: str
    geometry_type: str
    properties: dict[str, Any]
    sources: list[SourceSummaryData]


MAP_FEATURE_IDS_SQL = text(
    """
    WITH envelope AS (
        SELECT ST_MakeEnvelope(
            :min_lon, :min_lat, :max_lon, :max_lat, 4326
        ) AS geom
    )
    SELECT object.id
    FROM catalog.objects AS object
    CROSS JOIN envelope
    WHERE object.lifecycle_status = 'active'
      AND object.geom && envelope.geom
      AND ST_Intersects(object.geom, envelope.geom)
      AND EXISTS (
          SELECT 1
          FROM catalog.object_categories AS filter_category
          WHERE filter_category.object_id = object.id
            AND filter_category.lifecycle_status = 'active'
            AND filter_category.category_key = ANY(:categories)
      )
    LIMIT :fetch_limit
    """
)

MAP_FEATURE_PAYLOAD_SQL = text(
    """
    SELECT object.id,
           object.name,
           object.object_kind,
           ST_AsGeoJSON(object.geom, 6)::jsonb AS geometry,
           ARRAY(
               SELECT all_category.category_key
               FROM catalog.object_categories AS all_category
               WHERE all_category.object_id = object.id
                 AND all_category.lifecycle_status = 'active'
               ORDER BY all_category.category_key
           ) AS categories
    FROM catalog.objects AS object
    WHERE object.id = ANY(:object_ids)
      AND object.lifecycle_status = 'active'
    """
)

OBJECT_DETAIL_SQL = text(
    """
    SELECT object.id,
           object.name,
           object.object_kind,
           replace(ST_GeometryType(object.geom), 'ST_', '') AS geometry_type,
           object.properties,
           ARRAY(
               SELECT category.category_key
               FROM catalog.object_categories AS category
               WHERE category.object_id = object.id
                 AND category.lifecycle_status = 'active'
               ORDER BY category.category_key
           ) AS categories
    FROM catalog.objects AS object
    WHERE object.id = :object_id
      AND object.lifecycle_status = 'active'
    """
)

OBJECT_SOURCES_SQL = text(
    """
    SELECT source.provider,
           binding.source_object_type AS object_type,
           binding.source_object_id AS object_id,
           coalesce(binding.source_native_version, source.version) AS source_version,
           binding.geometry_quality
    FROM catalog.object_sources AS binding
    JOIN meta.dataset_sources AS source ON source.id = binding.source_id
    WHERE binding.object_id = :object_id
      AND binding.source_status = 'present'
    ORDER BY source.provider, binding.source_object_type, binding.source_object_id
    """
)


def _geometry(value: Any) -> dict[str, Any]:
    parsed = json.loads(value) if isinstance(value, str) else value
    if not isinstance(parsed, dict):
        raise ValueError("PostGIS returned invalid GeoJSON geometry")
    return {str(key): item for key, item in parsed.items()}


class MapCatalogService:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def features(
        self, bbox: BoundingBox, categories: tuple[str, ...], limit: int
    ) -> list[MapFeatureData]:
        with self.engine.connect() as connection:
            enabled = set(
                connection.execute(
                    text(
                        "SELECT key FROM catalog.categories "
                        "WHERE enabled AND key = ANY(:categories)"
                    ),
                    {"categories": list(categories)},
                ).scalars()
            )
            unknown = sorted(set(categories) - enabled)
            if unknown:
                raise UnknownCategoriesError(unknown)
            object_ids = connection.execute(
                MAP_FEATURE_IDS_SQL,
                {
                    "min_lon": bbox.min_lon,
                    "min_lat": bbox.min_lat,
                    "max_lon": bbox.max_lon,
                    "max_lat": bbox.max_lat,
                    "categories": list(categories),
                    "fetch_limit": limit + 1,
                },
            ).scalars().all()
            if len(object_ids) > limit:
                raise FeatureLimitExceededError(limit)
            if not object_ids:
                return []
            rows = connection.execute(
                MAP_FEATURE_PAYLOAD_SQL, {"object_ids": object_ids}
            ).all()
        return sorted(
            [
                MapFeatureData(
                    id=row.id,
                    name=str(row.name) if row.name is not None else None,
                    object_kind=str(row.object_kind),
                    geometry=_geometry(row.geometry),
                    categories=[str(category) for category in row.categories],
                )
                for row in rows
            ],
            key=lambda feature: str(feature.id),
        )

    def object_detail(self, object_id: UUID) -> ObjectDetailData | None:
        with self.engine.connect() as connection:
            row = connection.execute(
                OBJECT_DETAIL_SQL, {"object_id": object_id}
            ).one_or_none()
            if row is None:
                return None
            source_rows = connection.execute(
                OBJECT_SOURCES_SQL, {"object_id": object_id}
            ).all()
        return ObjectDetailData(
            id=row.id,
            name=str(row.name) if row.name is not None else None,
            categories=[str(category) for category in row.categories],
            object_kind=str(row.object_kind),
            geometry_type=str(row.geometry_type),
            properties=dict(row.properties),
            sources=[
                SourceSummaryData(
                    provider=str(source.provider),
                    object_type=str(source.object_type),
                    object_id=str(source.object_id),
                    source_version=(
                        str(source.source_version)
                        if source.source_version is not None
                        else None
                    ),
                    geometry_quality=str(source.geometry_quality),
                )
                for source in source_rows
            ],
        )
