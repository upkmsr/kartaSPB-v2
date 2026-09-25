from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.map_validation import MapRequestValidationError, parse_districts
from app.api.schemas import ErrorDetail, ErrorResponse, SearchResult, SearchResultList
from app.api.search_validation import parse_optional_categories, parse_search_query
from app.data.districts import UnknownDistrictsError
from app.data.map_catalog import UnknownCategoriesError
from app.data.search_catalog import SearchCatalogService
from app.db.session import get_engine

router = APIRouter()


def get_search_catalog_service() -> SearchCatalogService:
    return SearchCatalogService(get_engine())


def _error(detail: ErrorDetail) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail=detail.model_dump(mode="json", exclude_none=True),
    )


@router.get(
    "/search",
    response_model=SearchResultList,
    responses={422: {"model": ErrorResponse}},
    summary="Search active canonical objects by name",
)
def search(
    service: Annotated[SearchCatalogService, Depends(get_search_catalog_service)],
    q: Annotated[
        str,
        Query(
            description="Name query; 3-100 characters after normalization",
            json_schema_extra={"minLength": 3, "maxLength": 100},
        ),
    ],
    categories: Annotated[
        str | None, Query(description="Optional comma-separated category keys")
    ] = None,
    districts: Annotated[
        str | None, Query(description="Optional comma-separated domain district UUIDs")
    ] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> SearchResultList:
    try:
        parsed_query = parse_search_query(q)
        parsed_categories = parse_optional_categories(categories)
        parsed_districts = parse_districts(districts)
    except MapRequestValidationError as exc:
        raise _error(ErrorDetail(code="invalid_request", message=str(exc))) from exc
    try:
        results = service.search(
            parsed_query, parsed_categories, parsed_districts, limit
        )
    except UnknownCategoriesError as exc:
        raise _error(
            ErrorDetail(
                code="unknown_category",
                message="One or more categories are unknown or disabled",
                unknown_categories=exc.categories,
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
    return SearchResultList(
        results=[
            SearchResult(
                id=result.id,
                name=result.name,
                categories=result.categories,
                object_kind=result.object_kind,
                geometry_type=result.geometry_type,
                representative_point=result.representative_point,
                bbox=result.bbox,
            )
            for result in results
        ]
    )
