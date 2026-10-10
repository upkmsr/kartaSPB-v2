import os

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, text

INDEX_NAME = "ix_analytics_analysis_cells_grid_district_cell"


def _index_count(engine: Engine) -> int:
    with engine.connect() as connection:
        return int(
            connection.scalar(
                text(
                    "SELECT count(*) FROM pg_indexes "
                    "WHERE schemaname='analytics' AND indexname=:name"
                ),
                {"name": INDEX_NAME},
            )
            or 0
        )


@pytest.mark.integration
def test_covering_index_upgrade_downgrade_and_data_invariance() -> None:
    database_url = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL")
    if database_url is None:
        pytest.skip("Set TEST_DATABASE_URL to run migration integration tests")
    engine = create_engine(database_url)
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url)

    with engine.connect() as connection:
        before = connection.execute(
            text(
                "SELECT (SELECT count(*) FROM analytics.analysis_cells), "
                "(SELECT count(*) FROM analytics.metric_runs), "
                "(SELECT count(*) FROM analytics.cell_metric_values), "
                "(SELECT count(*) FROM analytics.metric_score_runs), "
                "(SELECT count(*) FROM analytics.cell_metric_scores)"
            )
        ).one()
    assert _index_count(engine) == 1

    engine.dispose()
    command.downgrade(config, "20261005_0014")
    engine = create_engine(database_url)
    assert _index_count(engine) == 0
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == (
            "20261005_0014"
        )
        assert connection.execute(
            text(
                "SELECT (SELECT count(*) FROM analytics.analysis_cells), "
                "(SELECT count(*) FROM analytics.metric_runs), "
                "(SELECT count(*) FROM analytics.cell_metric_values), "
                "(SELECT count(*) FROM analytics.metric_score_runs), "
                "(SELECT count(*) FROM analytics.cell_metric_scores)"
            )
        ).one() == before

    engine.dispose()
    command.upgrade(config, "head")
    engine = create_engine(database_url)
    assert _index_count(engine) == 1
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == (
            "20261010_0016"
        )
        assert connection.execute(
            text(
                "SELECT (SELECT count(*) FROM analytics.analysis_cells), "
                "(SELECT count(*) FROM analytics.metric_runs), "
                "(SELECT count(*) FROM analytics.cell_metric_values), "
                "(SELECT count(*) FROM analytics.metric_score_runs), "
                "(SELECT count(*) FROM analytics.cell_metric_scores)"
            )
        ).one() == before
    engine.dispose()
