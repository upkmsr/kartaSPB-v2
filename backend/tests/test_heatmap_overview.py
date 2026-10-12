from uuid import UUID

from app.analytics.heatmap import HeatmapService
from app.analytics.scoring.engine import ScoringMetric, ScoringPlan


def plan() -> ScoringPlan:
    return ScoringPlan(
        grid_version="spb-square-200m-v1",
        metrics=(
            ScoringMetric("education.school.accessibility_index", UUID(int=1), "a", 40),
            ScoringMetric("nature.park.accessibility_index", UUID(int=2), "b", 60),
        ),
        scoring_signature="c" * 64,
        cell_count=36292,
        total_weight=100,
    )


def test_overview_tiles_average_the_final_composite_score() -> None:
    statement, params = HeatmapService.tile_statement(plan(), 9, 298, 149)
    sql = str(statement)
    assert "avg(score) AS score" in sql
    assert "ST_Collect(geom) AS geom" in sql
    assert "aggregated" in sql
    assert params["aggregation_factor"] == 4


def test_detail_tiles_keep_exact_cells_without_overview_aggregation() -> None:
    statement, params = HeatmapService.tile_statement(plan(), 12, 2392, 1188)
    sql = str(statement)
    assert "avg(score) AS score" not in sql
    assert "ST_Collect(geom) AS geom" not in sql
    assert "aggregation_factor" not in params
