"""Add logical facility representation groups.

Revision ID: 20260929_0009
Revises: 20260928_0008
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260929_0009"
down_revision: str | None = "20260928_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "facility_entities",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("category_key", sa.String(length=96), nullable=False),
        sa.Column("representative_object_id", postgresql.UUID(as_uuid=True)),
        sa.Column("display_object_id", postgresql.UUID(as_uuid=True)),
        sa.Column("analysis_object_id", postgresql.UUID(as_uuid=True)),
        sa.Column(
            "lifecycle_status",
            sa.String(length=16),
            server_default="active",
            nullable=False,
        ),
        sa.Column("link_method", sa.String(length=255), nullable=False),
        sa.Column(
            "evidence",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "lifecycle_status IN ('active','inactive')",
            name=op.f("ck_facility_entities_lifecycle_status"),
        ),
        sa.CheckConstraint(
            "lifecycle_status <> 'active' OR "
            "(representative_object_id IS NOT NULL AND display_object_id IS NOT NULL "
            "AND analysis_object_id IS NOT NULL)",
            name=op.f("ck_facility_entities_active_roles"),
        ),
        sa.ForeignKeyConstraint(
            ["category_key"], ["catalog.categories.key"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["representative_object_id"], ["catalog.objects.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["display_object_id"], ["catalog.objects.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["analysis_object_id"], ["catalog.objects.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="domain",
    )
    op.create_index(
        "ix_domain_facility_entities_category_status",
        "facility_entities",
        ["category_key", "lifecycle_status"],
        schema="domain",
    )
    op.create_index(
        "ix_domain_facility_entities_display",
        "facility_entities",
        ["display_object_id"],
        schema="domain",
    )

    op.create_table(
        "facility_entity_members",
        sa.Column("facility_entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("canonical_object_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("geometry_role", sa.String(length=24), nullable=False),
        sa.Column(
            "lifecycle_status",
            sa.String(length=16),
            server_default="active",
            nullable=False,
        ),
        sa.Column("link_method", sa.String(length=255), nullable=False),
        sa.Column(
            "evidence",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "geometry_role IN ('POINT','FACILITY_SITE','BUILDING','OTHER_AREA','UNKNOWN')",
            name=op.f("ck_facility_entity_members_geometry_role"),
        ),
        sa.CheckConstraint(
            "lifecycle_status IN ('active','inactive')",
            name=op.f("ck_facility_entity_members_lifecycle_status"),
        ),
        sa.ForeignKeyConstraint(
            ["facility_entity_id"], ["domain.facility_entities.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["canonical_object_id"], ["catalog.objects.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("facility_entity_id", "canonical_object_id"),
        schema="domain",
    )
    op.create_index(
        "ix_domain_facility_members_object_status",
        "facility_entity_members",
        ["canonical_object_id", "lifecycle_status"],
        schema="domain",
    )
    op.create_index(
        "uq_domain_facility_members_active_object",
        "facility_entity_members",
        ["canonical_object_id"],
        unique=True,
        schema="domain",
        postgresql_where=sa.text("lifecycle_status = 'active'"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_domain_facility_members_active_object",
        table_name="facility_entity_members",
        schema="domain",
    )
    op.drop_index(
        "ix_domain_facility_members_object_status",
        table_name="facility_entity_members",
        schema="domain",
    )
    op.drop_table("facility_entity_members", schema="domain")
    op.drop_index(
        "ix_domain_facility_entities_display",
        table_name="facility_entities",
        schema="domain",
    )
    op.drop_index(
        "ix_domain_facility_entities_category_status",
        table_name="facility_entities",
        schema="domain",
    )
    op.drop_table("facility_entities", schema="domain")
