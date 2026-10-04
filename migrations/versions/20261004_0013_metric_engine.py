"""Add the universal metric publication engine.

Revision ID: 20261004_0013
Revises: 20261004_0012
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261004_0013"
down_revision: str | None = "20261004_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "metric_runs",
        sa.Column("run_id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("metric_key", sa.String(length=200), nullable=False),
        sa.Column("definition_version", sa.String(length=100), nullable=False),
        sa.Column("calculation_version", sa.String(length=100), nullable=False),
        sa.Column("grid_version", sa.String(length=100), nullable=False),
        sa.Column("definition_checksum", sa.CHAR(length=64), nullable=False),
        sa.Column("input_fingerprint", sa.CHAR(length=64), nullable=False),
        sa.Column("definition_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("run_signature", sa.CHAR(length=64), nullable=False),
        sa.Column("cell_count", sa.Integer(), nullable=False),
        sa.Column("min_value", sa.Float(), nullable=False),
        sa.Column("max_value", sa.Float(), nullable=False),
        sa.Column("mean_value", sa.Float(), nullable=False),
        sa.Column("values_checksum", sa.CHAR(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "btrim(metric_key) <> ''",
            name=op.f("ck_metric_runs_metric_key_not_blank"),
        ),
        sa.CheckConstraint(
            "btrim(grid_version) <> ''",
            name=op.f("ck_metric_runs_grid_version_not_blank"),
        ),
        sa.CheckConstraint(
            "cell_count > 0", name=op.f("ck_metric_runs_cell_count_positive")
        ),
        sa.CheckConstraint(
            "definition_checksum ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_metric_runs_definition_checksum"),
        ),
        sa.CheckConstraint(
            "input_fingerprint ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_metric_runs_input_fingerprint"),
        ),
        sa.CheckConstraint(
            "run_signature ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_metric_runs_run_signature"),
        ),
        sa.CheckConstraint(
            "values_checksum ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_metric_runs_values_checksum"),
        ),
        sa.PrimaryKeyConstraint("run_id", name=op.f("pk_metric_runs")),
        sa.UniqueConstraint("run_signature", name=op.f("uq_metric_runs_run_signature")),
        schema="analytics",
    )
    op.create_index(
        "ix_analytics_metric_runs_metric_grid",
        "metric_runs",
        ["metric_key", "grid_version"],
        schema="analytics",
    )
    op.create_table(
        "cell_metric_values",
        sa.Column("run_id", sa.UUID(), nullable=False),
        sa.Column("cell_id", sa.String(length=160), nullable=False),
        sa.Column("raw_value", sa.Float(), nullable=False),
        sa.CheckConstraint(
            "raw_value = raw_value AND raw_value NOT IN "
            "('Infinity'::double precision, '-Infinity'::double precision)",
            name=op.f("ck_cell_metric_values_raw_value_finite"),
        ),
        sa.ForeignKeyConstraint(
            ["cell_id"], ["analytics.analysis_cells.cell_id"],
            name=op.f("fk_cell_metric_values_cell_id_analysis_cells"), ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"], ["analytics.metric_runs.run_id"],
            name=op.f("fk_cell_metric_values_run_id_metric_runs"), ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("run_id", "cell_id", name=op.f("pk_cell_metric_values")),
        schema="analytics",
    )
    op.create_index(
        "ix_analytics_cell_metric_values_cell_id",
        "cell_metric_values",
        ["cell_id"],
        schema="analytics",
    )
    op.create_table(
        "metric_current_runs",
        sa.Column("metric_key", sa.String(length=200), nullable=False),
        sa.Column("grid_version", sa.String(length=100), nullable=False),
        sa.Column("run_id", sa.UUID(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["run_id"], ["analytics.metric_runs.run_id"],
            name=op.f("fk_metric_current_runs_run_id_metric_runs"), ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("metric_key", "grid_version", name=op.f("pk_metric_current_runs")),
        sa.UniqueConstraint("run_id", name=op.f("uq_metric_current_runs_run_id")),
        schema="analytics",
    )
    op.execute(
        """
        CREATE FUNCTION analytics.reject_metric_history_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION '% is append-only', TG_TABLE_NAME;
        END;
        $$
        """
    )
    for table_name in ("metric_runs", "cell_metric_values"):
        op.execute(
            f"""
            CREATE TRIGGER trg_{table_name}_append_only
            BEFORE UPDATE OR DELETE ON analytics.{table_name}
            FOR EACH ROW EXECUTE FUNCTION analytics.reject_metric_history_mutation()
            """
        )


def downgrade() -> None:
    for table_name in ("cell_metric_values", "metric_runs"):
        op.execute(f"DROP TRIGGER trg_{table_name}_append_only ON analytics.{table_name}")
    op.execute("DROP FUNCTION analytics.reject_metric_history_mutation()")
    op.drop_table("metric_current_runs", schema="analytics")
    op.drop_index(
        "ix_analytics_cell_metric_values_cell_id",
        table_name="cell_metric_values",
        schema="analytics",
    )
    op.drop_table("cell_metric_values", schema="analytics")
    op.drop_index(
        "ix_analytics_metric_runs_metric_grid",
        table_name="metric_runs",
        schema="analytics",
    )
    op.drop_table("metric_runs", schema="analytics")
