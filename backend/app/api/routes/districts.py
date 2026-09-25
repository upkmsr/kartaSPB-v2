from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.schemas.districts import DistrictList, DistrictSummary
from app.data.districts import DistrictCatalogService
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
