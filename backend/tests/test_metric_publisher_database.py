import math
import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError

from app.analytics.metrics.contracts import MetricDefinition
from app.analytics.metrics.publisher import MetricPublishError, publish_metric


def database_url() -> str:
    value = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL")
    if value is None:
        pytest.skip("Set TEST_DATABASE_URL to run metric publisher integration tests")
    return value


def definition(key: str) -> MetricDefinition:
    return MetricDefinition.model_validate(
        {
            "key": key,
            "definition_version": "1",
            "label": "Synthetic fixture",
            "description": "Integration test only",
            "group": "test",
            "unit": "index",
            "value_semantics": "index",
            "preferred_direction": "context_only",
            "provider_key": "test.synthetic",
            "calculation_version": "1",
        }
    )


@pytest.mark.integration
def test_metric_publication_is_atomic_complete_idempotent_and_append_only() -> None:
    engine = create_engine(database_url())
    suffix = uuid4().hex
    grid_version = f"test-grid-{suffix}"
    metric = definition(f"test.synthetic.m{suffix}")
    object_id = uuid4()
    district_id = uuid4()
    cell_ids = [f"{grid_version}:{index}" for index in range(3)]

    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO catalog.objects "
                "(id, object_kind, lifecycle_status, name, geom, properties, "
                "property_sources, revision) VALUES "
                "(:id, 'boundary', 'active', 'F7 fixture', "
                "ST_MakeEnvelope(30, 60, 30.01, 60.01, 4326), '{}', '{}', 1)"
            ),
            {"id": object_id},
        )
        connection.execute(
            text(
                "INSERT INTO domain.districts "
                "(id, canonical_object_id, name, slug, display_order, enabled) "
                "VALUES (:id, :object_id, 'F7 fixture', :slug, "
                "(SELECT min(candidate) FROM generate_series(10000, 32767) "
                "AS candidates(candidate) "
                "LEFT JOIN domain.districts AS existing "
                "ON existing.display_order = candidate "
                "WHERE existing.id IS NULL), false)"
            ),
            {"id": district_id, "object_id": object_id, "slug": f"f7-{suffix}"},
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

    initial = [(cell_ids[0], -2.0), (cell_ids[1], 0.0), (cell_ids[2], 4.0)]
    first = publish_metric(engine, metric, grid_version, "a" * 64, initial)
    repeated = publish_metric(engine, metric, grid_version, "a" * 64, reversed(initial))
    assert first.status == "created"
    assert repeated.status == "unchanged"
    assert repeated.run_id == first.run_id
    assert first.cell_count == 3
    assert first.minimum == -2.0
    assert first.maximum == 4.0
    assert first.mean == pytest.approx(2 / 3)

    with pytest.raises(MetricPublishError, match="different values"):
        publish_metric(
            engine,
            metric,
            grid_version,
            "a" * 64,
            [(cell_ids[0], -1.0), (cell_ids[1], 0.0), (cell_ids[2], 4.0)],
        )
    with pytest.raises(MetricPublishError, match="definition checksum"):
        publish_metric(
            engine,
            metric,
            grid_version,
            "c" * 64,
            initial,
            definition_checksum="f" * 64,
        )

    changed = publish_metric(
        engine,
        metric,
        grid_version,
        "b" * 64,
        [(cell_ids[0], -1.0), (cell_ids[1], 1.0), (cell_ids[2], 5.0)],
    )
    assert changed.run_id != first.run_id
    with engine.connect() as connection:
        assert connection.scalar(
            text(
                "SELECT count(*) FROM analytics.metric_runs "
                "WHERE metric_key = :key AND grid_version = :grid_version"
            ),
            {"key": metric.key, "grid_version": grid_version},
        ) == 2
        assert connection.scalar(
            text(
                "SELECT run_id FROM analytics.metric_current_runs "
                "WHERE metric_key = :key AND grid_version = :grid_version"
            ),
            {"key": metric.key, "grid_version": grid_version},
        ) == changed.run_id

    for invalid_values, message in [
        (initial[:2], "missing=1, extra=0"),
        (initial + [("not-a-cell", 1.0)], "missing=0, extra=1"),
        (initial + [(cell_ids[0], 9.0)], "duplicate cell value"),
        ([(cell_ids[0], math.nan), *initial[1:]], "non-finite value"),
        ([(cell_ids[0], math.inf), *initial[1:]], "non-finite value"),
    ]:
        with pytest.raises(MetricPublishError, match=message):
            publish_metric(engine, metric, grid_version, uuid4().hex * 2, invalid_values)

    with engine.connect() as connection:
        pointer = connection.scalar(
            text(
                "SELECT run_id FROM analytics.metric_current_runs "
                "WHERE metric_key = :key AND grid_version = :grid_version"
            ),
            {"key": metric.key, "grid_version": grid_version},
        )
    assert pointer == changed.run_id

    with pytest.raises(DBAPIError, match="append-only"), engine.begin() as connection:
        connection.execute(
            text("UPDATE analytics.metric_runs SET cell_count = 1 WHERE run_id = :run_id"),
            {"run_id": first.run_id},
        )
    with pytest.raises(DBAPIError, match="append-only"), engine.begin() as connection:
        connection.execute(
            text("DELETE FROM analytics.cell_metric_values WHERE run_id = :run_id"),
            {"run_id": first.run_id},
        )
    engine.dispose()
