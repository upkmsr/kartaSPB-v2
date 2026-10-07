import base64
import json
import math
import os
from math import asinh, pi, tan
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError

from app.analytics.heatmap import HeatmapError, HeatmapService
from app.analytics.metrics.contracts import MetricDefinition
from app.analytics.metrics.publisher import publish_metric
from app.analytics.metrics.registry import MetricRegistry
from app.analytics.scoring.contracts import NormalizationDefinition
from app.analytics.scoring.engine import ScoringError, ScoringService
from app.analytics.scoring.publisher import (
    NormalizationPublishError,
    publish_normalized_metric,
)
from app.analytics.scoring.registry import NormalizationRegistry


def database_url() -> str:
    value = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL")
    if value is None:
        pytest.skip("Set TEST_DATABASE_URL to run scoring integration tests")
    return value


def metric(key: str, direction: str) -> MetricDefinition:
    return MetricDefinition.model_validate(
        {
            "key": key,
            "definition_version": "1",
            "label": "F9 fixture",
            "description": "Integration test only",
            "group": "test",
            "unit": "index",
            "value_semantics": "index",
            "preferred_direction": direction,
            "provider_key": "test.synthetic",
            "calculation_version": "1",
        }
    )


def normalization(
    key: str, points: list[list[float]], *, version: str = "1"
) -> NormalizationDefinition:
    return NormalizationDefinition.model_validate(
        {
            "metric_key": key,
            "normalization_version": version,
            "label": "F9 fixture",
            "method": "piecewise_linear",
            "points": points,
            "enabled": True,
            "notes": "Integration test only",
        }
    )


@pytest.mark.integration
def test_normalized_publication_and_weighted_scoring_lifecycle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_engine(database_url())
    suffix = uuid4().hex
    grid_version = f"test-score-grid-{suffix}"
    first_metric = metric(f"test.score.low{suffix}", "lower_better")
    second_metric = metric(f"test.score.high{suffix}", "higher_better")
    first_normalization = normalization(
        first_metric.key, [[0, 100], [10, 50], [20, 0]]
    )
    second_normalization = normalization(
        second_metric.key, [[0, 0], [10, 50], [20, 100]]
    )
    registry = NormalizationRegistry(
        [first_normalization, second_normalization],
        MetricRegistry([first_metric, second_metric]),
    )
    object_id = uuid4()
    district_id = uuid4()
    cell_ids = [f"{grid_version}:{index}" for index in range(3)]

    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO catalog.objects "
                "(id, object_kind, lifecycle_status, name, geom, properties, "
                "property_sources, revision) VALUES "
                "(:id, 'boundary', 'active', 'F9 fixture', "
                "ST_MakeEnvelope(30, 60, 30.01, 60.01, 4326), '{}', '{}', 1)"
            ),
            {"id": object_id},
        )
        connection.execute(
            text(
                "INSERT INTO domain.districts "
                "(id, canonical_object_id, name, slug, display_order, enabled) "
                "VALUES (:id, :object_id, 'F9 fixture', :slug, "
                "(SELECT min(candidate) FROM generate_series(10000, 32767) "
                "AS candidates(candidate) LEFT JOIN domain.districts AS existing "
                "ON existing.display_order = candidate WHERE existing.id IS NULL), false)"
            ),
            {"id": district_id, "object_id": object_id, "slug": f"f9-{suffix}"},
        )
        for index, cell_id in enumerate(cell_ids):
            x = 500000 + index * 200
            connection.execute(
                text(
                    "INSERT INTO analytics.analysis_cells "
                    "(cell_id, grid_version, grid_i, grid_j, cell_size_m, district_id, "
                    "center, center_metric, geom, geom_metric) VALUES "
                    "(:cell_id, :grid_version, :grid_i, 0, 200, :district_id, "
                    "ST_Transform(ST_SetSRID(ST_MakePoint(:x + 100, 6650100), 32636), 4326), "
                    "ST_SetSRID(ST_MakePoint(:x + 100, 6650100), 32636), "
                    "ST_Transform(ST_MakeEnvelope(:x, 6650000, :x + 200, 6650200, 32636), 4326), "
                    "ST_MakeEnvelope(:x, 6650000, :x + 200, 6650200, 32636))"
                ),
                {
                    "cell_id": cell_id,
                    "grid_version": grid_version,
                    "grid_i": index,
                    "district_id": district_id,
                    "x": x,
                },
            )

    values = list(zip(cell_ids, [0.0, 10.0, 20.0], strict=True))
    publish_metric(engine, first_metric, grid_version, "a" * 64, values)
    publish_metric(engine, second_metric, grid_version, "b" * 64, values)
    first = publish_normalized_metric(engine, first_normalization, grid_version)
    second = publish_normalized_metric(engine, second_normalization, grid_version)
    repeated = publish_normalized_metric(engine, first_normalization, grid_version)
    assert first.status == "created"
    assert second.status == "created"
    assert repeated.status == "unchanged"
    assert repeated.score_run_id == first.score_run_id
    assert (first.minimum, first.maximum, first.mean) == (0, 100, 50)

    service = ScoringService(engine, registry)
    one = service.evaluate(grid_version, {first_metric.key: 100})
    assert (one.minimum, one.maximum, one.mean) == (0, 100, 50)
    assert [cell.score for cell in one.top_cells] == [100, 50, 0]
    equal = service.evaluate(
        grid_version, {first_metric.key: 100, second_metric.key: 100}
    )
    assert (equal.minimum, equal.maximum, equal.mean) == (50, 50, 50)
    reversed_order = service.evaluate(
        grid_version, {second_metric.key: 100, first_metric.key: 100}
    )
    assert reversed_order.scoring_signature == equal.scoring_signature
    unequal = service.evaluate(
        grid_version, {first_metric.key: 100, second_metric.key: 50}
    )
    assert unequal.scoring_signature != equal.scoring_signature
    assert 0 <= unequal.minimum <= unequal.mean <= unequal.maximum <= 100

    heatmap = HeatmapService(engine, service)
    prepared = heatmap.prepare(
        grid_version, {second_metric.key: 100, first_metric.key: 100}
    )
    assert prepared.scoring_signature == equal.scoring_signature
    assert prepared.spec == heatmap.prepare(
        grid_version, {first_metric.key: 100, second_metric.key: 100}
    ).spec
    with engine.connect() as connection:
        lon, lat = connection.execute(
            text(
                "SELECT ST_X(center), ST_Y(center) FROM analytics.analysis_cells "
                "WHERE cell_id = :cell_id"
            ),
            {"cell_id": cell_ids[0]},
        ).one()
        immutable_counts_before = connection.execute(
            text(
                "SELECT (SELECT count(*) FROM analytics.metric_runs), "
                "(SELECT count(*) FROM analytics.cell_metric_values), "
                "(SELECT count(*) FROM analytics.metric_score_runs), "
                "(SELECT count(*) FROM analytics.cell_metric_scores), "
                "(SELECT count(*) FROM analytics.metric_score_current_runs), "
                "(SELECT count(*) FROM analytics.analysis_cells)"
            )
        ).one()
    z = 12
    x = int((lon + 180) / 360 * (1 << z))
    y = int((1 - asinh(tan(lat * pi / 180)) / pi) / 2 * (1 << z))
    tile = heatmap.tile(prepared.scoring_signature, z, x, y, prepared.spec)
    assert tile.payload
    assert heatmap.tile(prepared.scoring_signature, z, x, y, prepared.spec).payload == tile.payload
    assert b"analysis_heatmap" in tile.payload
    assert b"cell_id" in tile.payload
    assert b"district_id" in tile.payload
    assert b"score" in tile.payload
    assert heatmap.tile(prepared.scoring_signature, 12, 0, 0, prepared.spec).payload == b""
    with pytest.raises(HeatmapError, match="does not match"):
        heatmap.tile("f" * 64, z, x, y, prepared.spec)

    raw_spec = json.loads(
        base64.urlsafe_b64decode(prepared.spec + "=" * (-len(prepared.spec) % 4))
    )
    raw_spec["metrics"][0]["score_run_id"] = str(uuid4())
    unknown_run_spec = base64.urlsafe_b64encode(
        json.dumps(raw_spec, sort_keys=True, separators=(",", ":")).encode()
    ).rstrip(b"=").decode()
    with pytest.raises(HeatmapError, match="not found"):
        heatmap.plan_from_spec(unknown_run_spec)

    raw_spec = json.loads(
        base64.urlsafe_b64decode(prepared.spec + "=" * (-len(prepared.spec) % 4))
    )
    raw_spec["metrics"][0]["score_run_id"], raw_spec["metrics"][1]["score_run_id"] = (
        raw_spec["metrics"][1]["score_run_id"],
        raw_spec["metrics"][0]["score_run_id"],
    )
    wrong_metric_spec = base64.urlsafe_b64encode(
        json.dumps(raw_spec, sort_keys=True, separators=(",", ":")).encode()
    ).rstrip(b"=").decode()
    with pytest.raises(HeatmapError, match="does not belong"):
        heatmap.plan_from_spec(wrong_metric_spec)

    prepared_plan = heatmap.plan_from_spec(prepared.spec)
    selected_sql = ",".join(
        f"(CAST(:run_{index} AS uuid), CAST(:weight_{index} AS double precision))"
        for index, _metric in enumerate(prepared_plan.metrics)
    )
    score_params: dict[str, object] = {
        "cell_id": equal.top_cells[0].cell_id,
        "total_weight": prepared_plan.total_weight,
    }
    for index, selected_metric in enumerate(prepared_plan.metrics):
        score_params[f"run_{index}"] = str(selected_metric.score_run_id)
        score_params[f"weight_{index}"] = selected_metric.weight
    with engine.connect() as connection:
        tile_formula_score = connection.scalar(
            text(
                "WITH selected(score_run_id,weight) AS (VALUES "
                + selected_sql
                + ") SELECT (sum(score.score::numeric * selected.weight::numeric) / "
                "CAST(:total_weight AS numeric))::double precision "
                "FROM analytics.cell_metric_scores score JOIN selected "
                "ON selected.score_run_id=score.score_run_id "
                "WHERE score.cell_id=:cell_id"
            ),
            score_params,
        )
    assert math.isclose(tile_formula_score, equal.top_cells[0].score, abs_tol=1e-12)
    with engine.connect() as connection:
        immutable_counts_after = connection.execute(
            text(
                "SELECT (SELECT count(*) FROM analytics.metric_runs), "
                "(SELECT count(*) FROM analytics.cell_metric_values), "
                "(SELECT count(*) FROM analytics.metric_score_runs), "
                "(SELECT count(*) FROM analytics.cell_metric_scores), "
                "(SELECT count(*) FROM analytics.metric_score_current_runs), "
                "(SELECT count(*) FROM analytics.analysis_cells)"
            )
        ).one()
    assert immutable_counts_after == immutable_counts_before
    with pytest.raises(ScoringError, match="positive"):
        service.evaluate(grid_version, {first_metric.key: 0})

    changed_raw = publish_metric(
        engine,
        first_metric,
        grid_version,
        "c" * 64,
        list(zip(cell_ids, [0.0, 5.0, 20.0], strict=True)),
    )
    changed_score = publish_normalized_metric(engine, first_normalization, grid_version)
    assert changed_score.metric_run_id == changed_raw.run_id
    assert changed_score.score_run_id != first.score_run_id
    changed_signature = service.evaluate(
        grid_version, {first_metric.key: 100, second_metric.key: 100}
    ).scoring_signature
    assert changed_signature != equal.scoring_signature
    assert heatmap.plan_from_spec(prepared.spec).scoring_signature == equal.scoring_signature
    assert heatmap.tile(prepared.scoring_signature, z, x, y, prepared.spec).payload

    version_two = normalization(
        first_metric.key, [[0, 100], [10, 40], [20, 0]], version="2"
    )
    version_two_run = publish_normalized_metric(engine, version_two, grid_version)
    assert version_two_run.score_run_id != changed_score.score_run_id
    with pytest.raises(ScoringError, match="does not match enabled normalization"):
        service.evaluate(grid_version, {first_metric.key: 100})
    with engine.connect() as connection:
        assert connection.scalar(
            text(
                "SELECT count(*) FROM analytics.metric_score_runs "
                "WHERE metric_key = :metric_key AND grid_version = :grid_version"
            ),
            {"metric_key": first_metric.key, "grid_version": grid_version},
        ) == 3
        assert connection.scalar(
            text(
                "SELECT count(*) FROM analytics.metric_runs "
                "WHERE metric_key = :metric_key AND grid_version = :grid_version"
            ),
            {"metric_key": first_metric.key, "grid_version": grid_version},
        ) == 2

    partial_score_run_id = uuid4()
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO analytics.metric_score_runs "
                "(score_run_id,metric_key,grid_version,metric_run_id,normalization_version,"
                "normalization_checksum,normalization_snapshot,run_signature,cell_count,"
                "score_min,score_max,score_mean,values_checksum) VALUES "
                "(:score_run_id,:metric_key,:grid_version,:metric_run_id,'1',"
                ":checksum,CAST(:snapshot AS jsonb),:signature,3,0,100,50,:values_checksum)"
            ),
            {
                "score_run_id": partial_score_run_id,
                "metric_key": first_metric.key,
                "grid_version": grid_version,
                "metric_run_id": changed_score.metric_run_id,
                "checksum": first_normalization.checksum(),
                "snapshot": first_normalization.canonical_json(),
                "signature": "e" * 64,
                "values_checksum": "d" * 64,
            },
        )
        connection.execute(
            text(
                "INSERT INTO analytics.cell_metric_scores (score_run_id,cell_id,score) "
                "VALUES (:run,:cell0,100),(:run,:cell1,50)"
            ),
            {"run": partial_score_run_id, "cell0": cell_ids[0], "cell1": cell_ids[1]},
        )
        connection.execute(
            text(
                "UPDATE analytics.metric_score_current_runs SET score_run_id=:run "
                "WHERE metric_key=:metric_key AND grid_version=:grid_version"
            ),
            {
                "run": partial_score_run_id,
                "metric_key": first_metric.key,
                "grid_version": grid_version,
            },
        )
    with pytest.raises(ScoringError, match="incomplete"):
        service.evaluate(grid_version, {first_metric.key: 100})

    with pytest.raises(NormalizationPublishError, match="checksum"):
        publish_normalized_metric(
            engine, first_normalization, grid_version, normalization_checksum="f" * 64
        )
    monkeypatch.setattr(
        NormalizationDefinition, "normalize", lambda _self, _raw_value: math.nan
    )
    with pytest.raises(NormalizationPublishError, match="invalid score"):
        publish_normalized_metric(engine, first_normalization, grid_version)

    with pytest.raises(DBAPIError, match="append-only"), engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE analytics.metric_score_runs SET cell_count = 1 "
                "WHERE score_run_id = :score_run_id"
            ),
            {"score_run_id": first.score_run_id},
        )
    with pytest.raises(DBAPIError, match="append-only"), engine.begin() as connection:
        connection.execute(
            text(
                "DELETE FROM analytics.cell_metric_scores "
                "WHERE score_run_id = :score_run_id"
            ),
            {"score_run_id": first.score_run_id},
        )
    engine.dispose()
