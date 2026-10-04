"""Add the versioned Saint Petersburg analysis grid.

Revision ID: 20261004_0012
Revises: 20261003_0011
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geometry

revision: str = "20261004_0012"
down_revision: str | None = "20261003_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "analysis_cells",
        sa.Column("cell_id", sa.String(length=160), nullable=False),
        sa.Column("grid_version", sa.String(length=100), nullable=False),
        sa.Column("grid_i", sa.Integer(), nullable=False),
        sa.Column("grid_j", sa.Integer(), nullable=False),
        sa.Column("cell_size_m", sa.Integer(), nullable=False),
        sa.Column("district_id", sa.UUID(), nullable=False),
        sa.Column(
            "center",
            Geometry("POINT", srid=4326, spatial_index=False),
            nullable=False,
        ),
        sa.Column(
            "center_metric",
            Geometry("POINT", srid=32636, spatial_index=False),
            nullable=False,
        ),
        sa.Column(
            "geom",
            Geometry("POLYGON", srid=4326, spatial_index=False),
            nullable=False,
        ),
        sa.Column(
            "geom_metric",
            Geometry("POLYGON", srid=32636, spatial_index=False),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "btrim(cell_id) <> ''", name=op.f("ck_analysis_cells_cell_id_not_blank")
        ),
        sa.CheckConstraint(
            "btrim(grid_version) <> ''",
            name=op.f("ck_analysis_cells_grid_version_not_blank"),
        ),
        sa.CheckConstraint(
            "cell_size_m > 0", name=op.f("ck_analysis_cells_cell_size_positive")
        ),
        sa.ForeignKeyConstraint(
            ["district_id"],
            ["domain.districts.id"],
            name=op.f("fk_analysis_cells_district_id_districts"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("cell_id", name=op.f("pk_analysis_cells")),
        sa.UniqueConstraint(
            "grid_version",
            "grid_i",
            "grid_j",
            name=op.f("uq_analysis_cells_grid_version"),
        ),
        schema="analytics",
    )
    op.create_index(
        "ix_analytics_analysis_cells_geom_gist",
        "analysis_cells",
        ["geom"],
        schema="analytics",
        postgresql_using="gist",
    )
    op.create_index(
        "ix_analytics_analysis_cells_center_metric_gist",
        "analysis_cells",
        ["center_metric"],
        schema="analytics",
        postgresql_using="gist",
    )
    op.create_index(
        "ix_analytics_analysis_cells_grid_version",
        "analysis_cells",
        ["grid_version"],
        schema="analytics",
    )
    op.create_index(
        "ix_analytics_analysis_cells_district_id",
        "analysis_cells",
        ["district_id"],
        schema="analytics",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_analytics_analysis_cells_district_id",
        table_name="analysis_cells",
        schema="analytics",
    )
    op.drop_index(
        "ix_analytics_analysis_cells_grid_version",
        table_name="analysis_cells",
        schema="analytics",
    )
    op.drop_index(
        "ix_analytics_analysis_cells_center_metric_gist",
        table_name="analysis_cells",
        schema="analytics",
    )
    op.drop_index(
        "ix_analytics_analysis_cells_geom_gist",
        table_name="analysis_cells",
        schema="analytics",
    )
    op.drop_table("analysis_cells", schema="analytics")
