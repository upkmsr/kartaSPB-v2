"""Add the universal normalization and scoring engine.

Revision ID: 20261005_0014
Revises: 20261004_0013
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261005_0014"
down_revision: str | None = "20261004_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "metric_score_runs",
        sa.Column(
            "score_run_id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("metric_key", sa.String(length=200), nullable=False),
        sa.Column("grid_version", sa.String(length=100), nullable=False),
        sa.Column("metric_run_id", sa.UUID(), nullable=False),
        sa.Column("normalization_version", sa.String(length=100), nullable=False),
        sa.Column("normalization_checksum", sa.CHAR(length=64), nullable=False),
        sa.Column(
            "normalization_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("run_signature", sa.CHAR(length=64), nullable=False),
        sa.Column("cell_count", sa.Integer(), nullable=False),
        sa.Column("score_min", sa.Float(), nullable=False),
        sa.Column("score_max", sa.Float(), nullable=False),
        sa.Column("score_mean", sa.Float(), nullable=False),
        sa.Column("values_checksum", sa.CHAR(length=64), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "btrim(metric_key) <> ''",
            name=op.f("ck_metric_score_runs_metric_key_not_blank"),
        ),
        sa.CheckConstraint(
            "btrim(grid_version) <> ''",
            name=op.f("ck_metric_score_runs_grid_version_not_blank"),
        ),
        sa.CheckConstraint(
            "cell_count > 0",
            name=op.f("ck_metric_score_runs_cell_count_positive"),
        ),
        sa.CheckConstraint(
            "normalization_checksum ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_metric_score_runs_normalization_checksum"),
        ),
        sa.CheckConstraint(
            "run_signature ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_metric_score_runs_run_signature"),
        ),
        sa.CheckConstraint(
            "values_checksum ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_metric_score_runs_values_checksum"),
        ),
        sa.CheckConstraint(
            "score_min >= 0",
            name=op.f("ck_metric_score_runs_score_min_nonnegative"),
        ),
        sa.CheckConstraint(
            "score_max <= 100",
            name=op.f("ck_metric_score_runs_score_max_at_most_100"),
        ),
        sa.CheckConstraint(
            "score_min <= score_mean",
            name=op.f("ck_metric_score_runs_score_min_le_mean"),
        ),
        sa.CheckConstraint(
            "score_mean <= score_max",
            name=op.f("ck_metric_score_runs_score_mean_le_max"),
        ),
        sa.ForeignKeyConstraint(
            ["metric_run_id"], ["analytics.metric_runs.run_id"],
            name=op.f("fk_metric_score_runs_metric_run_id_metric_runs"), ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("score_run_id", name=op.f("pk_metric_score_runs")),
        sa.UniqueConstraint("run_signature", name=op.f("uq_metric_score_runs_run_signature")),
        schema="analytics",
    )
    op.create_index(
        "ix_analytics_metric_score_runs_metric_grid",
        "metric_score_runs",
        ["metric_key", "grid_version"],
        schema="analytics",
    )
    op.create_table(
        "cell_metric_scores",
        sa.Column("score_run_id", sa.UUID(), nullable=False),
        sa.Column("cell_id", sa.String(length=160), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.CheckConstraint(
            "score = score AND score NOT IN "
            "('Infinity'::double precision, '-Infinity'::double precision)",
            name=op.f("ck_cell_metric_scores_score_finite"),
        ),
        sa.CheckConstraint(
            "score >= 0 AND score <= 100",
            name=op.f("ck_cell_metric_scores_score_in_range"),
        ),
        sa.ForeignKeyConstraint(
            ["cell_id"], ["analytics.analysis_cells.cell_id"],
            name=op.f("fk_cell_metric_scores_cell_id_analysis_cells"), ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["score_run_id"], ["analytics.metric_score_runs.score_run_id"],
            name=op.f("fk_cell_metric_scores_score_run_id_metric_score_runs"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "score_run_id", "cell_id", name=op.f("pk_cell_metric_scores")
        ),
        schema="analytics",
    )
    op.create_index(
        "ix_analytics_cell_metric_scores_cell_id",
        "cell_metric_scores",
        ["cell_id"],
        schema="analytics",
    )
    op.create_table(
        "metric_score_current_runs",
        sa.Column("metric_key", sa.String(length=200), nullable=False),
        sa.Column("grid_version", sa.String(length=100), nullable=False),
        sa.Column("score_run_id", sa.UUID(), nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["score_run_id"], ["analytics.metric_score_runs.score_run_id"],
            name=op.f("fk_metric_score_current_runs_score_run_id_metric_score_runs"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "metric_key", "grid_version", name=op.f("pk_metric_score_current_runs")
        ),
        sa.UniqueConstraint(
            "score_run_id", name=op.f("uq_metric_score_current_runs_score_run_id")
        ),
        schema="analytics",
    )
    op.execute(
        """
        CREATE FUNCTION analytics.reject_metric_score_history_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION '% is append-only', TG_TABLE_NAME;
        END;
        $$
        """
    )
    for table_name in ("metric_score_runs", "cell_metric_scores"):
        op.execute(
            f"""
            CREATE TRIGGER trg_{table_name}_append_only
            BEFORE UPDATE OR DELETE ON analytics.{table_name}
            FOR EACH ROW EXECUTE FUNCTION analytics.reject_metric_score_history_mutation()
            """
        )


def downgrade() -> None:
    for table_name in ("cell_metric_scores", "metric_score_runs"):
        op.execute(f"DROP TRIGGER trg_{table_name}_append_only ON analytics.{table_name}")
    op.execute("DROP FUNCTION analytics.reject_metric_score_history_mutation()")
    op.drop_table("metric_score_current_runs", schema="analytics")
    op.drop_index(
        "ix_analytics_cell_metric_scores_cell_id",
        table_name="cell_metric_scores",
        schema="analytics",
    )
    op.drop_table("cell_metric_scores", schema="analytics")
    op.drop_index(
        "ix_analytics_metric_score_runs_metric_grid",
        table_name="metric_score_runs",
        schema="analytics",
    )
    op.drop_table("metric_score_runs", schema="analytics")
