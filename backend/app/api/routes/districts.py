from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.map_validation import MapRequestValidationError, parse_districts
from app.api.schemas.districts import (
    DistrictGeometry,
    DistrictGeometryFeature,
    DistrictGeometryFeatureCollection,
    DistrictGeometryProperties,
    DistrictList,
    DistrictSummary,
)
from app.api.schemas.map import ErrorDetail, ErrorResponse
from app.data.districts import DistrictCatalogService, UnknownDistrictsError
from app.db.session import get_engine

router = APIRouter()


def get_district_catalog_service() -> DistrictCatalogService:
    return DistrictCatalogService(get_engine())


@router.get(
    "/districts",
    response_model=DistrictList,
    summary="List enabled Saint Petersburg districts",
    description=(
        "Returns stable application district IDs and lightweight bounding boxes. "
        "Exact district geometry remains internal spatial truth."
    ),
)
def districts(
    service: Annotated[DistrictCatalogService, Depends(get_district_catalog_service)],
) -> DistrictList:
    return DistrictList(
        districts=[
            DistrictSummary(
                id=item.id,
                name=item.name,
                slug=item.slug,
                bbox=item.bbox,
                display_order=item.display_order,
            )
            for item in service.districts()
        ]
    )


def _error(detail: ErrorDetail) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail=detail.model_dump(mode="json", exclude_none=True),
    )


@router.get(
    "/districts/geometry",
    response_model=DistrictGeometryFeatureCollection,
    responses={422: {"model": ErrorResponse}},
    summary="Get exact selected district geometry",
    description=(
        "Returns one GeoJSON FeatureCollection for requested enabled district UUIDs. "
        "Geometry comes from each district's bound canonical catalog object."
    ),
)
def district_geometry(
    service: Annotated[DistrictCatalogService, Depends(get_district_catalog_service)],
    districts: Annotated[
        str,
        Query(description="Comma-separated domain district UUIDs; duplicates are normalized"),
    ],
) -> DistrictGeometryFeatureCollection:
    try:
        district_ids = parse_districts(districts)
    except MapRequestValidationError as exc:
        raise _error(ErrorDetail(code="invalid_request", message=str(exc))) from exc
    try:
        features = service.geometries(district_ids)
    except UnknownDistrictsError as exc:
        raise _error(
            ErrorDetail(
                code="unknown_district",
                message="One or more districts are unknown or disabled",
                unknown_districts=exc.unknown or None,
                disabled_districts=exc.disabled or None,
            )
        ) from exc
    return DistrictGeometryFeatureCollection(
        features=[
            DistrictGeometryFeature(
                id=feature.id,
                properties=DistrictGeometryProperties(
                    id=feature.id,
                    name=feature.name,
                    slug=feature.slug,
                ),
                geometry=DistrictGeometry.model_validate(feature.geometry),
            )
            for feature in features
        ]
    )
