"""Add import profile provenance and scope-aware OSM membership.

Revision ID: 20260928_0008
Revises: 20260925_0007
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260928_0008"
down_revision: str | None = "20260925_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        op.f("ck_import_runs_status_allowed"),
        "import_runs",
        schema="meta",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_import_runs_status_allowed"),
        "import_runs",
        "status IN ('pending', 'running', 'staged', 'success', 'failed')",
        schema="meta",
    )
    op.add_column("import_runs", sa.Column("profile", sa.String(length=100)), schema="meta")
    op.add_column(
        "import_runs",
        sa.Column(
            "authoritative_snapshot", sa.Boolean(), server_default=sa.false(), nullable=False
        ),
        schema="meta",
    )
    op.add_column(
        "import_runs",
        sa.Column("lifecycle_finalized_at", sa.DateTime(timezone=True)),
        schema="meta",
    )
    op.create_index(
        "ix_meta_import_runs_source_profile",
        "import_runs",
        ["source_id", "profile", "id"],
        schema="meta",
    )

    op.create_table(
        "osm_profile_memberships",
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("profile", sa.String(length=100), nullable=False),
        sa.Column("source_object_type", sa.String(length=16), nullable=False),
        sa.Column("source_object_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "lifecycle_status", sa.String(length=16), server_default="present", nullable=False
        ),
        sa.Column("first_seen_import_run_id", sa.Integer(), nullable=False),
        sa.Column("last_seen_import_run_id", sa.Integer(), nullable=False),
        sa.Column("missing_since", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "source_object_type IN ('node', 'way', 'relation')",
            name="ck_osm_profile_memberships_object_type",
        ),
        sa.CheckConstraint(
            "lifecycle_status IN ('present', 'missing')",
            name="ck_osm_profile_memberships_lifecycle_status",
        ),
        sa.ForeignKeyConstraint(
            ["source_id"], ["meta.dataset_sources.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["first_seen_import_run_id"], ["meta.import_runs.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["last_seen_import_run_id"], ["meta.import_runs.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint(
            "source_id", "profile", "source_object_type", "source_object_id"
        ),
        schema="meta",
    )
    op.create_index(
        "ix_meta_osm_profile_memberships_snapshot",
        "osm_profile_memberships",
        ["source_id", "profile", "last_seen_import_run_id"],
        schema="meta",
    )
    op.create_index(
        "ix_meta_osm_profile_memberships_active_identity",
        "osm_profile_memberships",
        ["source_id", "source_object_type", "source_object_id"],
        schema="meta",
        postgresql_where=sa.text("lifecycle_status = 'present'"),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_meta_osm_profile_memberships_active_identity",
        table_name="osm_profile_memberships",
        schema="meta",
    )
    op.drop_index(
        "ix_meta_osm_profile_memberships_snapshot",
        table_name="osm_profile_memberships",
        schema="meta",
    )
    op.drop_table("osm_profile_memberships", schema="meta")
    op.drop_index(
        "ix_meta_import_runs_source_profile", table_name="import_runs", schema="meta"
    )
    op.drop_column("import_runs", "lifecycle_finalized_at", schema="meta")
    op.drop_column("import_runs", "authoritative_snapshot", schema="meta")
    op.drop_column("import_runs", "profile", schema="meta")
    op.drop_constraint(
        op.f("ck_import_runs_status_allowed"),
        "import_runs",
        schema="meta",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_import_runs_status_allowed"),
        "import_runs",
        "status IN ('pending', 'running', 'success', 'failed')",
        schema="meta",
    )
