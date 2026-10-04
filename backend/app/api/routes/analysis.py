from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Response, status

from app.api.schemas.analysis import AnalysisGridMeta
from app.data.analysis_grid import AnalysisGridService
from app.db.session import get_engine

router = APIRouter(prefix="/analysis")


def get_analysis_grid_service() -> AnalysisGridService:
    return AnalysisGridService(get_engine())


@router.get("/grid/meta", response_model=AnalysisGridMeta)
def grid_meta(
    service: Annotated[AnalysisGridService, Depends(get_analysis_grid_service)],
) -> AnalysisGridMeta:
    return AnalysisGridMeta.model_validate(service.metadata(), from_attributes=True)


@router.get("/grid/tiles/{z}/{x}/{y}.mvt")
def grid_tile(
    z: Annotated[int, Path(ge=0, le=22)],
    x: Annotated[int, Path(ge=0)],
    y: Annotated[int, Path(ge=0)],
    service: Annotated[AnalysisGridService, Depends(get_analysis_grid_service)],
) -> Response:
    tile_limit = 1 << z
    if x >= tile_limit or y >= tile_limit:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Tile coordinate is outside the zoom extent",
        )
    return Response(
        content=service.tile(z, x, y),
        media_type="application/vnd.mapbox-vector-tile",
        headers={"Cache-Control": "public, max-age=86400"},
    )
