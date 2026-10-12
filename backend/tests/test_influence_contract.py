from uuid import UUID

import pytest

from app.analytics.influence import InfluenceError, InfluenceService
from app.analytics.scoring.engine import ScoringMetric, ScoringPlan


class FakeScoring:
    def resolve_current_plan(
        self, grid_version: str, weights: dict[str, float]
    ) -> ScoringPlan:
        metrics = tuple(
            ScoringMetric(
                metric_key=key,
                score_run_id=UUID(int=index + 1),
                run_signature=str(index),
                weight=weight,
            )
            for index, (key, weight) in enumerate(sorted(weights.items()))
        )
        return ScoringPlan(grid_version, metrics, "c" * 64, 36292, sum(weights.values()))


def test_prepare_rejects_duplicates_and_non_scenario_metrics() -> None:
    allowed = {"education.school.accessibility_index", "nature.park.accessibility_index"}
    service = InfluenceService(None, FakeScoring(), allowed)  # type: ignore[arg-type]
    with pytest.raises(InfluenceError, match="unique"):
        service.prepare("grid", ["nature.park.accessibility_index"] * 2)
    with pytest.raises(InfluenceError, match="unsupported"):
        service.prepare("grid", ["unknown.metric"])


def test_prepare_is_order_independent_and_emits_one_channel_per_run() -> None:
    allowed = {"education.school.accessibility_index", "nature.park.accessibility_index"}
    service = InfluenceService(None, FakeScoring(), allowed)  # type: ignore[arg-type]
    first = service.prepare("grid", list(allowed))
    second = service.prepare("grid", list(reversed(list(allowed))))
    assert first.spec == second.spec
    assert first.influence_signature == second.influence_signature
    assert [channel.property_name for channel in first.channels] == ["score_0", "score_1"]
    assert all(channel.score_run_id for channel in first.channels)


def test_tile_sql_reads_immutable_scores_once_and_keeps_channels_separate() -> None:
    allowed = {"education.school.accessibility_index", "nature.park.accessibility_index"}
    service = InfluenceService(None, FakeScoring(), allowed)  # type: ignore[arg-type]
    plan = FakeScoring().resolve_current_plan("grid", {key: 1 for key in allowed})
    statement, params = service.tile_statement(plan, 11, 1196, 594)
    sql = str(statement)
    assert "analytics.cell_metric_scores" in sql
    assert "score_0" in sql and "score_1" in sql
    assert "sum(score" not in sql.lower()
    assert "INSERT" not in sql.upper() and "UPDATE" not in sql.upper()
    assert params["grid_version"] == "grid"
