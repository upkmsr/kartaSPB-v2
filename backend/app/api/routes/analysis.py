from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status

from app.analytics.grid import GRID_VERSION
from app.analytics.heatmap import (
    HEATMAP_DELIVERY_VERSION,
    HeatmapError,
    HeatmapService,
)
from app.analytics.metrics.registry import MetricRegistry
from app.analytics.scoring.contracts import NormalizationDefinition
from app.analytics.scoring.engine import ScoringError, ScoringService
from app.analytics.scoring.registry import NormalizationRegistry
from app.api.schemas.analysis import (
    AnalysisGridMeta,
    CurrentMetricRunPublic,
    HeatmapPreparePublic,
    HeatmapPrepareRequest,
    MetricDefinitionPublic,
    NormalizationDefinitionPublic,
    NormalizationPointPublic,
    ScoreEvaluationPublic,
    ScoreEvaluationRequest,
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


def get_normalization_registry() -> NormalizationRegistry:
    return NormalizationRegistry.load()


def get_scoring_service() -> ScoringService:
    return ScoringService(get_engine(), get_normalization_registry())


def get_heatmap_service() -> HeatmapService:
    engine = get_engine()
    return HeatmapService(engine, ScoringService(engine, get_normalization_registry()))


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


def _public_normalization(
    definition: NormalizationDefinition,
) -> NormalizationDefinitionPublic:
    return NormalizationDefinitionPublic(
        metric_key=definition.metric_key,
        normalization_version=definition.normalization_version,
        label=definition.label,
        method=str(definition.method),
        points=[
            NormalizationPointPublic(raw_value=point.raw_value, score=point.score)
            for point in definition.points
        ],
        checksum=definition.checksum(),
    )


@router.get(
    "/scoring/normalizations", response_model=list[NormalizationDefinitionPublic]
)
def list_normalizations(
    registry: Annotated[NormalizationRegistry, Depends(get_normalization_registry)],
) -> list[NormalizationDefinitionPublic]:
    return [_public_normalization(definition) for definition in registry.list()]


@router.get(
    "/scoring/normalizations/{metric_key}", response_model=NormalizationDefinitionPublic
)
def normalization_definition(
    metric_key: str,
    registry: Annotated[NormalizationRegistry, Depends(get_normalization_registry)],
) -> NormalizationDefinitionPublic:
    definition = registry.get(metric_key)
    if definition is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Normalization not found"
        )
    return _public_normalization(definition)


@router.post("/scoring/evaluate", response_model=ScoreEvaluationPublic)
def evaluate_score(
    request: ScoreEvaluationRequest,
    service: Annotated[ScoringService, Depends(get_scoring_service)],
) -> ScoreEvaluationPublic:
    try:
        result = service.evaluate(
            request.grid_version or GRID_VERSION,
            request.weights,
            limit=request.limit,
        )
    except ScoringError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    return ScoreEvaluationPublic.model_validate(result.to_dict())


@router.post("/heatmap/prepare", response_model=HeatmapPreparePublic)
def prepare_heatmap(
    request: HeatmapPrepareRequest,
    service: Annotated[HeatmapService, Depends(get_heatmap_service)],
) -> HeatmapPreparePublic:
    try:
        prepared = service.prepare(request.grid_version or GRID_VERSION, request.weights)
    except HeatmapError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    return HeatmapPreparePublic.model_validate(prepared.to_dict())


@router.get("/heatmap/tiles/{scoring_signature}/{z}/{x}/{y}.mvt")
def heatmap_tile(
    scoring_signature: Annotated[
        str, Path(min_length=64, max_length=64, pattern="^[0-9a-f]{64}$")
    ],
    z: Annotated[int, Path(ge=0, le=22)],
    x: Annotated[int, Path(ge=0)],
    y: Annotated[int, Path(ge=0)],
    spec: Annotated[str, Query(min_length=1, max_length=8192)],
    service: Annotated[HeatmapService, Depends(get_heatmap_service)],
) -> Response:
    tile_limit = 1 << z
    if x >= tile_limit or y >= tile_limit:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Tile coordinate is outside the zoom extent",
        )
    try:
        tile = service.tile(scoring_signature, z, x, y, spec)
    except HeatmapError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    return Response(
        content=tile.payload,
        media_type="application/vnd.mapbox-vector-tile",
        headers={
            "Cache-Control": "public, max-age=86400, immutable",
            "ETag": f'"{tile.etag}"',
            "X-KARTASPB-Scoring-Signature": tile.scoring_signature,
            "X-KARTASPB-Heatmap-Version": HEATMAP_DELIVERY_VERSION,
        },
    )
