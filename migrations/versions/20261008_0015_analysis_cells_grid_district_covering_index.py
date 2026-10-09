"""Add the district-scoped analysis-cell covering index.

Revision ID: 20261008_0015
Revises: 20261005_0014
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20261008_0015"
down_revision: str | None = "20261005_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

INDEX_NAME = "ix_analytics_analysis_cells_grid_district_cell"


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(
            f"CREATE INDEX CONCURRENTLY {INDEX_NAME} "
            "ON analytics.analysis_cells (grid_version, district_id, cell_id)"
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(f"DROP INDEX CONCURRENTLY analytics.{INDEX_NAME}")
