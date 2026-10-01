"""Add entity-aware search normalization and logical streets.

Revision ID: 20261001_0010
Revises: 20260929_0009
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geometry
from sqlalchemy.dialects import postgresql

revision: str = "20261001_0010"
down_revision: str | None = "20260929_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SEARCH_NORMALIZATION_SQL = (
    "btrim(regexp_replace(replace(lower(translate(normalize(name, NFKC), "
    "'Ёё', 'Ее')), chr(160), ' '), '[[:space:]]+', ' ', 'g'))"
)


def upgrade() -> None:
    op.add_column(
        "objects",
        sa.Column(
            "search_name_v2",
            sa.Text(),
            sa.Computed(SEARCH_NORMALIZATION_SQL, persisted=True),
        ),
        schema="catalog",
    )
    op.create_index(
        "ix_catalog_objects_search_name_v2_trgm",
        "objects",
        ["search_name_v2"],
        schema="catalog",
        postgresql_using="gin",
        postgresql_ops={"search_name_v2": "gin_trgm_ops"},
        postgresql_where=sa.text(
            "lifecycle_status = 'active' AND search_name_v2 IS NOT NULL"
        ),
    )

    op.create_table(
        "street_entities",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("search_name", sa.Text(), nullable=False),
        sa.Column(
            "geom",
            Geometry("MULTILINESTRING", srid=4326, spatial_index=False),
            nullable=True,
        ),
        sa.Column(
            "representative_point",
            Geometry("POINT", srid=4326, spatial_index=False),
            nullable=True,
        ),
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
            name=op.f("ck_street_entities_lifecycle_status"),
        ),
        sa.CheckConstraint(
            "lifecycle_status <> 'active' OR "
            "(geom IS NOT NULL AND representative_point IS NOT NULL "
            "AND NOT ST_IsEmpty(geom) AND ST_IsValid(geom))",
            name=op.f("ck_street_entities_active_geometry"),
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="domain",
    )
    op.create_index(
        "ix_domain_street_entities_search_name_trgm",
        "street_entities",
        ["search_name"],
        schema="domain",
        postgresql_using="gin",
        postgresql_ops={"search_name": "gin_trgm_ops"},
        postgresql_where=sa.text("lifecycle_status = 'active'"),
    )
    op.create_index(
        "ix_domain_street_entities_geom_gist",
        "street_entities",
        ["geom"],
        schema="domain",
        postgresql_using="gist",
        postgresql_where=sa.text("lifecycle_status = 'active'"),
    )

    op.create_table(
        "street_entity_members",
        sa.Column("street_entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("canonical_object_id", postgresql.UUID(as_uuid=True), nullable=False),
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
            name=op.f("ck_street_entity_members_lifecycle_status"),
        ),
        sa.ForeignKeyConstraint(
            ["street_entity_id"], ["domain.street_entities.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["canonical_object_id"], ["catalog.objects.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("street_entity_id", "canonical_object_id"),
        schema="domain",
    )
    op.create_index(
        "ix_domain_street_members_object_status",
        "street_entity_members",
        ["canonical_object_id", "lifecycle_status"],
        schema="domain",
    )
    op.create_index(
        "uq_domain_street_members_active_object",
        "street_entity_members",
        ["canonical_object_id"],
        unique=True,
        schema="domain",
        postgresql_where=sa.text("lifecycle_status = 'active'"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_domain_street_members_active_object",
        table_name="street_entity_members",
        schema="domain",
    )
    op.drop_index(
        "ix_domain_street_members_object_status",
        table_name="street_entity_members",
        schema="domain",
    )
    op.drop_table("street_entity_members", schema="domain")
    op.drop_index(
        "ix_domain_street_entities_geom_gist",
        table_name="street_entities",
        schema="domain",
    )
    op.drop_index(
        "ix_domain_street_entities_search_name_trgm",
        table_name="street_entities",
        schema="domain",
    )
    op.drop_table("street_entities", schema="domain")
    op.drop_index(
        "ix_catalog_objects_search_name_v2_trgm",
        table_name="objects",
        schema="catalog",
    )
    op.drop_column("objects", "search_name_v2", schema="catalog")
