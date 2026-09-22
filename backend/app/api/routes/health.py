from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.db.health import ReadinessReport, check_readiness

router = APIRouter()


def get_readiness_report() -> ReadinessReport:
    return check_readiness()


@router.get("/live")
def live() -> dict[str, str]:
    return {"status": "live"}


@router.get("/ready", response_model=ReadinessReport)
def ready(
    response: Response,
    report: Annotated[ReadinessReport, Depends(get_readiness_report)],
) -> ReadinessReport:
    if report.status != "ready":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return report
