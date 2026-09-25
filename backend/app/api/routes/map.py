from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.map_validation import (
    MapRequestValidationError,
    parse_bbox,
    parse_categories,
    parse_districts,
)
from app.api.schemas import (
    ErrorDetail,
    ErrorResponse,
    GeoJSONFeature,
    GeoJSONFeatureCollection,
    MapFeatureProperties,
    ObjectDetail,
    SourceSummary,
)
from app.data.districts import UnknownDistrictsError
from app.data.map_catalog import (
    FeatureLimitExceededError,
    MapCatalogService,
    UnknownCategoriesError,
)
from app.db.session import get_engine

router = APIRouter()


def get_map_catalog_service() -> MapCatalogService:
    return MapCatalogService(get_engine())


def _error(detail: ErrorDetail) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail=detail.model_dump(mode="json", exclude_none=True),
    )


@router.get(
    "/map/features",
    response_model=GeoJSONFeatureCollection,
    responses={422: {"model": ErrorResponse}},
)
def map_features(
    service: Annotated[MapCatalogService, Depends(get_map_catalog_service)],
    bbox: Annotated[str, Query(description="minLon,minLat,maxLon,maxLat")],
    categories: Annotated[str, Query(description="Comma-separated category keys")],
    districts: Annotated[
        str | None,
        Query(
            description=(
                "Optional comma-separated domain district UUIDs. Duplicate IDs are normalized."
            )
        ),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=5000)] = 1000,
) -> GeoJSONFeatureCollection:
    try:
        parsed_bbox = parse_bbox(bbox)
        parsed_categories = parse_categories(categories)
        parsed_districts = parse_districts(districts)
    except MapRequestValidationError as exc:
        raise _error(ErrorDetail(code="invalid_request", message=str(exc))) from exc
    try:
        features = service.features(parsed_bbox, parsed_categories, limit, parsed_districts)
    except UnknownCategoriesError as exc:
        raise _error(
            ErrorDetail(
                code="unknown_category",
                message="One or more categories are unknown or disabled",
                unknown_categories=exc.categories,
            )
        ) from exc
    except FeatureLimitExceededError as exc:
        raise _error(
            ErrorDetail(
                code="feature_limit_exceeded",
                message="The viewport contains more features than the requested limit",
                requested_limit=exc.requested_limit,
                suggestion="zoom_in_or_disable_layers",
            )
        ) from exc
    except UnknownDistrictsError as exc:
        raise _error(
            ErrorDetail(
                code="unknown_district",
                message="One or more districts are unknown or disabled",
                unknown_districts=exc.unknown or None,
                disabled_districts=exc.disabled or None,
            )
        ) from exc
    return GeoJSONFeatureCollection(
        features=[
            GeoJSONFeature(
                id=feature.id,
                geometry=feature.geometry,
                properties=MapFeatureProperties(
                    canonical_id=feature.id,
                    name=feature.name,
                    categories=feature.categories,
                    object_kind=feature.object_kind,
                ),
            )
            for feature in features
        ]
    )


@router.get(
    "/objects/{object_id}",
    response_model=ObjectDetail,
    responses={404: {"description": "Active object not found"}},
)
def object_detail(
    object_id: UUID,
    service: Annotated[MapCatalogService, Depends(get_map_catalog_service)],
) -> ObjectDetail:
    detail = service.object_detail(object_id)
    if detail is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Object not found")
    return ObjectDetail(
        id=detail.id,
        name=detail.name,
        categories=detail.categories,
        object_kind=detail.object_kind,
        geometry_type=detail.geometry_type,
        properties=detail.properties,
        sources=[
            SourceSummary(
                provider=source.provider,
                object_type=source.object_type,
                object_id=source.object_id,
                source_version=source.source_version,
                geometry_quality=source.geometry_quality,
            )
            for source in detail.sources
        ],
    )
