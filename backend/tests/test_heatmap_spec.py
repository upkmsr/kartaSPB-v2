import base64
import json
from uuid import UUID

import pytest

from app.analytics.heatmap import (
    HEATMAP_SPEC_VERSION,
    HeatmapError,
    decode_heatmap_spec,
    encode_heatmap_spec,
)
from app.analytics.scoring.engine import ScoringMetric, ScoringPlan


def plan(*, second_weight: float = 50) -> ScoringPlan:
    return ScoringPlan(
        grid_version="spb-square-200m-v1",
        metrics=(
            ScoringMetric(
                metric_key="education.school.distance_m",
                score_run_id=UUID("00000000-0000-0000-0000-000000000001"),
                run_signature="a" * 64,
                weight=100,
            ),
            ScoringMetric(
                metric_key="nature.park.distance_m",
                score_run_id=UUID("00000000-0000-0000-0000-000000000002"),
                run_signature="b" * 64,
                weight=second_weight,
            ),
        ),
        scoring_signature="c" * 64,
        cell_count=36292,
        total_weight=100 + second_weight,
    )


def encoded(payload: object) -> str:
    return base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":")).encode()
    ).rstrip(b"=").decode()


def test_heatmap_spec_is_deterministic_url_safe_and_exact() -> None:
    first = encode_heatmap_spec(plan())
    second = encode_heatmap_spec(plan())
    assert first == second
    assert "=" not in first
    decoded = decode_heatmap_spec(first)
    assert decoded.grid_version == "spb-square-200m-v1"
    assert [metric.metric_key for metric in decoded.metrics] == [
        "education.school.distance_m",
        "nature.park.distance_m",
    ]
    assert [metric.weight for metric in decoded.metrics] == [100, 50]
    assert encode_heatmap_spec(plan(second_weight=40)) != first


@pytest.mark.parametrize(
    "spec, message",
    [
        ("not+base64", "base64url"),
        (encoded({"version": "future", "grid_version": "grid", "metrics": []}), "version"),
        (
            encoded(
                {
                    "version": HEATMAP_SPEC_VERSION,
                    "grid_version": "grid",
                    "metrics": [
                        {
                            "metric_key": f"test.metric{index}",
                            "score_run_id": "00000000-0000-0000-0000-000000000001",
                            "weight": "0x1.0000000000000p+0",
                        }
                        for index in range(13)
                    ],
                }
            ),
            "between 1 and 12",
        ),
    ],
)
def test_heatmap_spec_rejects_invalid_contracts(spec: str, message: str) -> None:
    with pytest.raises(HeatmapError, match=message):
        decode_heatmap_spec(spec)
