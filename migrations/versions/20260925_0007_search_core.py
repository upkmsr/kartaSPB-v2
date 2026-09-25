"""Add normalized trigram search support to canonical objects.

Revision ID: 20260925_0007
Revises: 20260925_0006
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260925_0007"
down_revision: str | None = "20260925_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.add_column(
        "objects",
        sa.Column(
            "search_name",
            sa.Text(),
            sa.Computed("lower(translate(name, 'Ёё', 'Ее'))", persisted=True),
        ),
        schema="catalog",
    )
    op.create_index(
        "ix_catalog_objects_search_name_trgm",
        "objects",
        ["search_name"],
        unique=False,
        schema="catalog",
        postgresql_using="gin",
        postgresql_ops={"search_name": "gin_trgm_ops"},
        postgresql_where=sa.text(
            "lifecycle_status = 'active' AND search_name IS NOT NULL"
        ),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_catalog_objects_search_name_trgm",
        table_name="objects",
        schema="catalog",
    )
    op.drop_column("objects", "search_name", schema="catalog")
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
