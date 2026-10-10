"""Add the cell-first score covering index used by scenario distributions.

Revision ID: 20261010_0016
Revises: 20261008_0015
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20261010_0016"
down_revision: str | None = "20261008_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD_INDEX = "ix_analytics_cell_metric_scores_cell_id"
NEW_INDEX = "ix_analytics_cell_metric_scores_cell_run_cover"


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(
            f"CREATE INDEX CONCURRENTLY {NEW_INDEX} "
            "ON analytics.cell_metric_scores (cell_id, score_run_id) INCLUDE (score)"
        )
        op.execute(f"DROP INDEX CONCURRENTLY analytics.{OLD_INDEX}")


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(
            f"CREATE INDEX CONCURRENTLY {OLD_INDEX} "
            "ON analytics.cell_metric_scores (cell_id)"
        )
        op.execute(f"DROP INDEX CONCURRENTLY analytics.{NEW_INDEX}")
