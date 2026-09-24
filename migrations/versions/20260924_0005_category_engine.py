"""Add the config-driven category engine persistence layer.

Revision ID: 20260924_0005
Revises: 20260924_0004
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260924_0005"
down_revision: str | None = "20260924_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "categories",
        sa.Column("key", sa.String(96), primary_key=True),
        sa.Column("parent_key", sa.String(96)),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column(
            "metadata", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["parent_key"], ["catalog.categories.key"], ondelete="RESTRICT"),
        schema="catalog",
    )
    op.create_table(
        "object_categories",
        sa.Column("object_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("category_key", sa.String(96), nullable=False),
        sa.Column("lifecycle_status", sa.String(16), server_default="active", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "lifecycle_status IN ('active','inactive')",
            name="ck_object_categories_lifecycle_status",
        ),
        sa.ForeignKeyConstraint(["object_id"], ["catalog.objects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["category_key"], ["catalog.categories.key"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("object_id", "category_key"),
        schema="catalog",
    )
    op.create_index(
        "ix_catalog_object_categories_category",
        "object_categories",
        ["category_key"],
        schema="catalog",
    )
    op.create_index(
        "ix_catalog_object_categories_category_status",
        "object_categories",
        ["category_key", "lifecycle_status"],
        schema="catalog",
    )
    op.create_table(
        "object_category_sources",
        sa.Column("object_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("category_key", sa.String(96), nullable=False),
        sa.Column("object_source_id", sa.BigInteger(), nullable=False),
        sa.Column("rule_id", sa.String(128), nullable=False),
        sa.Column("rule_version", sa.String(32), nullable=False),
        sa.Column("status", sa.String(16), server_default="active", nullable=False),
        sa.Column(
            "evidence", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        sa.Column("first_seen_import_run_id", sa.Integer(), nullable=False),
        sa.Column("last_seen_import_run_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('active','inactive')", name="ck_object_category_sources_status"
        ),
        sa.ForeignKeyConstraint(["object_id"], ["catalog.objects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["category_key"], ["catalog.categories.key"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["object_source_id"], ["catalog.object_sources.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["first_seen_import_run_id"], ["meta.import_runs.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["last_seen_import_run_id"], ["meta.import_runs.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("object_source_id", "category_key", "rule_id"),
        schema="catalog",
    )
    op.create_index(
        "ix_catalog_category_sources_object_category",
        "object_category_sources",
        ["object_id", "category_key", "status"],
        schema="catalog",
    )
    op.create_index(
        "ix_catalog_category_sources_rule",
        "object_category_sources",
        ["rule_id", "rule_version"],
        schema="catalog",
    )


def downgrade() -> None:
    op.drop_table("object_category_sources", schema="catalog")
    op.drop_table("object_categories", schema="catalog")
    op.drop_table("categories", schema="catalog")
