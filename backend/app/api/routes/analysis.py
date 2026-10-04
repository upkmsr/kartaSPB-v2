from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status

from app.analytics.grid import GRID_VERSION
from app.analytics.metrics.registry import MetricRegistry
from app.api.schemas.analysis import (
    AnalysisGridMeta,
    CurrentMetricRunPublic,
    MetricDefinitionPublic,
)
from app.data.analysis_grid import AnalysisGridService
from app.data.metrics import MetricQueryService
from app.db.session import get_engine

router = APIRouter(prefix="/analysis")


def get_analysis_grid_service() -> AnalysisGridService:
    return AnalysisGridService(get_engine())


def get_metric_registry() -> MetricRegistry:
    return MetricRegistry.load()


def get_metric_query_service() -> MetricQueryService:
    return MetricQueryService(get_engine())


def _public_definition(definition: object) -> MetricDefinitionPublic:
    return MetricDefinitionPublic.model_validate(definition, from_attributes=True)


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


@router.get("/metrics", response_model=list[MetricDefinitionPublic])
def list_metrics(
    registry: Annotated[MetricRegistry, Depends(get_metric_registry)],
) -> list[MetricDefinitionPublic]:
    return [_public_definition(definition) for definition in registry.list()]


@router.get("/metrics/{metric_key}", response_model=MetricDefinitionPublic)
def metric_definition(
    metric_key: str,
    registry: Annotated[MetricRegistry, Depends(get_metric_registry)],
) -> MetricDefinitionPublic:
    definition = registry.get(metric_key)
    if definition is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Metric not found")
    return _public_definition(definition)


@router.get("/metrics/{metric_key}/current", response_model=CurrentMetricRunPublic)
def current_metric_run(
    metric_key: str,
    registry: Annotated[MetricRegistry, Depends(get_metric_registry)],
    service: Annotated[MetricQueryService, Depends(get_metric_query_service)],
    grid_version: Annotated[str, Query(min_length=1)] = GRID_VERSION,
) -> CurrentMetricRunPublic:
    if registry.get(metric_key) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Metric not found")
    run = service.current(metric_key, grid_version)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Current metric run not found"
        )
    return CurrentMetricRunPublic.model_validate(run, from_attributes=True)
