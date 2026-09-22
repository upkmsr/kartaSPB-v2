"""Create PostGIS extension and metadata registry.

Revision ID: 20260922_0001
Revises:
Create Date: 2026-09-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260922_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMAS = ("meta", "staging", "catalog", "domain", "user", "analytics")


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    for schema in SCHEMAS:
        op.execute(sa.text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))

    op.create_table(
        "dataset_sources",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("provider", sa.String(length=200), nullable=False),
        sa.Column("source_type", sa.String(length=50), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("license", sa.String(length=200), nullable=True),
        sa.Column("attribution", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_dataset_sources")),
        sa.UniqueConstraint("name", name=op.f("uq_dataset_sources_name")),
        schema="meta",
    )

    op.create_table(
        "import_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_version", sa.String(length=200), nullable=True),
        sa.Column("checksum", sa.String(length=128), nullable=True),
        sa.Column("processed_count", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("inserted_count", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("updated_count", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("skipped_count", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("error_count", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column(
            "details",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'success', 'failed')",
            name=op.f("ck_import_runs_status_allowed"),
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["meta.dataset_sources.id"],
            name=op.f("fk_import_runs_source_id_dataset_sources"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_import_runs")),
        schema="meta",
    )
    op.create_index(
        op.f("ix_meta_import_runs_source_id"),
        "import_runs",
        ["source_id"],
        unique=False,
        schema="meta",
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_meta_import_runs_source_id"), table_name="import_runs", schema="meta"
    )
    op.drop_table("import_runs", schema="meta")
    op.drop_table("dataset_sources", schema="meta")
    for schema in reversed(SCHEMAS):
        op.execute(sa.text(f'DROP SCHEMA IF EXISTS "{schema}"'))
    # PostGIS is shared infrastructure and is intentionally retained on downgrade.
