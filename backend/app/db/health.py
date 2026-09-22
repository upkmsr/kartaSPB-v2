from pathlib import Path
from typing import Literal

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import get_engine


class ComponentStatus(BaseModel):
    status: Literal["ready", "unavailable", "outdated"]
    detail: str | None = None


class ReadinessReport(BaseModel):
    status: Literal["ready", "not_ready"]
    database: ComponentStatus
    postgis: ComponentStatus
    migrations: ComponentStatus


def _alembic_heads() -> set[str]:
    config_path = Path(__file__).resolve().parents[2] / "alembic.ini"
    config = Config(str(config_path))
    return set(ScriptDirectory.from_config(config).get_heads())


def check_readiness() -> ReadinessReport:
    unavailable = ComponentStatus(status="unavailable")
    try:
        with get_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
            database = ComponentStatus(status="ready")

            postgis_version = connection.scalar(text("SELECT PostGIS_Lib_Version()"))
            postgis = ComponentStatus(status="ready", detail=str(postgis_version))

            current_heads = set(MigrationContext.configure(connection).get_current_heads())
            expected_heads = _alembic_heads()
            if current_heads == expected_heads:
                migrations = ComponentStatus(
                    status="ready", detail=", ".join(sorted(current_heads))
                )
            else:
                migrations = ComponentStatus(
                    status="outdated",
                    detail=(
                        f"database={sorted(current_heads)} expected={sorted(expected_heads)}"
                    ),
                )
    except (SQLAlchemyError, OSError) as exc:
        return ReadinessReport(
            status="not_ready",
            database=ComponentStatus(status="unavailable", detail=type(exc).__name__),
            postgis=unavailable,
            migrations=unavailable,
        )

    overall = "ready" if migrations.status == "ready" else "not_ready"
    return ReadinessReport(
        status=overall,
        database=database,
        postgis=postgis,
        migrations=migrations,
    )
