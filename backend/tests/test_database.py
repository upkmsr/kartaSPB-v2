import os

import pytest
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text


@pytest.mark.integration
def test_database_postgis_and_migrations() -> None:
    database_url = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL")
    if database_url is None:
        pytest.skip("Set TEST_DATABASE_URL to run database integration tests")

    engine = create_engine(database_url)
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT 1")) == 1
        assert connection.scalar(text("SELECT PostGIS_Lib_Version()"))

        config = Config("alembic.ini")
        expected_heads = set(ScriptDirectory.from_config(config).get_heads())
        current_heads = set(MigrationContext.configure(connection).get_current_heads())

    assert current_heads == expected_heads
