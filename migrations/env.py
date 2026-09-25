from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import get_settings
from app.db.base import Base
from app.db.models import (  # noqa: F401
    CatalogObject,
    CatalogRelationship,
    DatasetSource,
    District,
    ImportRun,
    ObjectSource,
    OsmRelationGeometry,
)

config = context.config
config.set_main_option("sqlalchemy.url", get_settings().database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata
MANAGED_SCHEMAS = {
    "meta",
    "staging",
    "derived",
    "catalog",
    "domain",
    "user",
    "analytics",
}


def include_name(
    name: str | None, object_type: str, parent_names: dict[str, str | None]
) -> bool:
    """Keep PostGIS-owned schemas and tables outside Alembic autogenerate."""
    if object_type == "schema":
        return name in MANAGED_SCHEMAS
    if object_type == "table":
        return parent_names.get("schema_name") in MANAGED_SCHEMAS
    return True


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,
        include_name=include_name,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=True,
            include_name=include_name,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
