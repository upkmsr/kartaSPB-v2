import os

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, text

OLD_INDEX = "ix_analytics_cell_metric_scores_cell_id"
NEW_INDEX = "ix_analytics_cell_metric_scores_cell_run_cover"


def _index_definition(engine: Engine, name: str) -> str | None:
    with engine.connect() as connection:
        return connection.scalar(
            text(
                "SELECT indexdef FROM pg_indexes "
                "WHERE schemaname='analytics' AND indexname=:name"
            ),
            {"name": name},
        )


@pytest.mark.integration
def test_distribution_index_upgrade_downgrade_and_data_invariance() -> None:
    database_url = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL")
    if database_url is None:
        pytest.skip("Set TEST_DATABASE_URL to run migration integration tests")
    engine = create_engine(database_url)
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url)

    with engine.connect() as connection:
        before = connection.scalar(
            text("SELECT count(*) FROM analytics.cell_metric_scores")
        )
    definition = _index_definition(engine, NEW_INDEX)
    assert definition is not None
    assert "(cell_id, score_run_id) INCLUDE (score)" in definition
    assert _index_definition(engine, OLD_INDEX) is None

    engine.dispose()
    command.downgrade(config, "20261008_0015")
    engine = create_engine(database_url)
    assert _index_definition(engine, OLD_INDEX) is not None
    assert _index_definition(engine, NEW_INDEX) is None
    with engine.connect() as connection:
        after_downgrade = connection.scalar(
            text("SELECT count(*) FROM analytics.cell_metric_scores")
        )
        assert after_downgrade == before

    engine.dispose()
    command.upgrade(config, "head")
    engine = create_engine(database_url)
    assert _index_definition(engine, OLD_INDEX) is None
    assert _index_definition(engine, NEW_INDEX) is not None
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == (
            "20261010_0016"
        )
        after_upgrade = connection.scalar(
            text("SELECT count(*) FROM analytics.cell_metric_scores")
        )
        assert after_upgrade == before
    engine.dispose()
