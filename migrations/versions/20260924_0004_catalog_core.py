"""Add the provider-independent canonical GIS core.

Revision ID: 20260924_0004
Revises: 20260923_0003
Create Date: 2026-09-24
"""

from collections.abc import Sequence

import geoalchemy2
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260924_0004"
down_revision: str | None = "20260923_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "objects",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("object_kind", sa.String(24), nullable=False),
        sa.Column("lifecycle_status", sa.String(16), server_default="active", nullable=False),
        sa.Column("name", sa.Text()),
        sa.Column(
            "geom",
            geoalchemy2.types.Geometry(
                geometry_type="GEOMETRY", srid=4326, spatial_index=False
            ),
        ),
        sa.Column("name_source_id", sa.BigInteger()),
        sa.Column("geometry_source_id", sa.BigInteger()),
        sa.Column("geometry_locked", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column(
            "properties",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "property_sources",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("revision", sa.BigInteger(), server_default="1", nullable=False),
        sa.Column("superseded_by", postgresql.UUID(as_uuid=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("retired_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "object_kind IN ('feature', 'boundary')",
            name=op.f("ck_objects_object_kind"),
        ),
        sa.CheckConstraint(
            "lifecycle_status IN ('active', 'inactive', 'merged', 'retired')",
            name=op.f("ck_objects_lifecycle_status"),
        ),
        sa.CheckConstraint(
            "lifecycle_status <> 'active' OR "
            "(geom IS NOT NULL AND NOT ST_IsEmpty(geom) AND ST_IsValid(geom))",
            name=op.f("ck_objects_active_geometry"),
        ),
        sa.CheckConstraint(
            "superseded_by IS NULL OR superseded_by <> id",
            name=op.f("ck_objects_superseded_by_not_self"),
        ),
        sa.CheckConstraint(
            "lifecycle_status <> 'merged' OR superseded_by IS NOT NULL",
            name=op.f("ck_objects_merged_has_successor"),
        ),
        sa.ForeignKeyConstraint(
            ["superseded_by"], ["catalog.objects.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="catalog",
    )
    op.create_index(
        "ix_catalog_objects_geom_gist",
        "objects",
        ["geom"],
        postgresql_using="gist",
        schema="catalog",
    )
    op.create_index(
        "ix_catalog_objects_kind_status",
        "objects",
        ["object_kind", "lifecycle_status"],
        schema="catalog",
    )
    op.create_index(
        "ix_catalog_objects_properties_gin",
        "objects",
        ["properties"],
        postgresql_using="gin",
        schema="catalog",
    )
    op.create_index(
        "ix_catalog_objects_superseded_by",
        "objects",
        ["superseded_by"],
        schema="catalog",
    )

    op.create_table(
        "object_sources",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("object_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("source_object_type", sa.String(32), nullable=False),
        sa.Column("source_object_id", sa.Text(), nullable=False),
        sa.Column("source_native_version", sa.Text()),
        sa.Column("source_status", sa.String(16), server_default="present", nullable=False),
        sa.Column("candidate_name", sa.Text()),
        sa.Column(
            "candidate_geom",
            geoalchemy2.types.Geometry(
                geometry_type="GEOMETRY", srid=4326, spatial_index=False
            ),
        ),
        sa.Column(
            "candidate_properties",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("geometry_quality", sa.String(24), nullable=False),
        sa.Column("source_priority", sa.Integer(), server_default="0", nullable=False),
        sa.Column("match_method", sa.String(32), nullable=False),
        sa.Column("match_confidence", sa.Numeric(4, 3), nullable=False),
        sa.Column("first_seen_import_run_id", sa.Integer(), nullable=False),
        sa.Column("last_seen_import_run_id", sa.Integer(), nullable=False),
        sa.Column("last_changed_import_run_id", sa.Integer(), nullable=False),
        sa.Column("missing_since", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "source_status IN ('present', 'missing', 'deleted', 'superseded')",
            name=op.f("ck_object_sources_source_status"),
        ),
        sa.CheckConstraint(
            "candidate_geom IS NULL OR "
            "(NOT ST_IsEmpty(candidate_geom) AND ST_IsValid(candidate_geom))",
            name=op.f("ck_object_sources_candidate_geometry"),
        ),
        sa.CheckConstraint(
            "char_length(payload_hash) = 64",
            name=op.f("ck_object_sources_payload_hash"),
        ),
        sa.CheckConstraint(
            "match_confidence >= 0 AND match_confidence <= 1",
            name=op.f("ck_object_sources_match_confidence"),
        ),
        sa.ForeignKeyConstraint(
            ["object_id"], ["catalog.objects.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["source_id"], ["meta.dataset_sources.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["first_seen_import_run_id"], ["meta.import_runs.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["last_seen_import_run_id"], ["meta.import_runs.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["last_changed_import_run_id"], ["meta.import_runs.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_id",
            "source_object_type",
            "source_object_id",
            name="uq_object_sources_source_identity",
        ),
        schema="catalog",
    )
    op.create_index(
        "ix_catalog_object_sources_object_status",
        "object_sources",
        ["object_id", "source_status"],
        schema="catalog",
    )
    op.create_index(
        "ix_catalog_object_sources_candidate_geom_gist",
        "object_sources",
        ["candidate_geom"],
        postgresql_using="gist",
        schema="catalog",
    )
    op.create_index(
        "ix_catalog_object_sources_candidate_properties_gin",
        "object_sources",
        ["candidate_properties"],
        postgresql_using="gin",
        schema="catalog",
    )
    op.create_foreign_key(
        "fk_objects_name_source_id_object_sources",
        "objects",
        "object_sources",
        ["name_source_id"],
        ["id"],
        source_schema="catalog",
        referent_schema="catalog",
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_objects_geometry_source_id_object_sources",
        "objects",
        "object_sources",
        ["geometry_source_id"],
        ["id"],
        source_schema="catalog",
        referent_schema="catalog",
        ondelete="SET NULL",
    )

    op.create_table(
        "relationships",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("subject_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("relationship_type", sa.String(64), nullable=False),
        sa.Column("object_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provenance_object_source_id", sa.BigInteger()),
        sa.Column("derivation_method", sa.String(24), nullable=False),
        sa.Column("lifecycle_status", sa.String(16), server_default="active", nullable=False),
        sa.Column(
            "properties",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("first_seen_import_run_id", sa.Integer()),
        sa.Column("last_seen_import_run_id", sa.Integer()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("retired_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "subject_id <> object_id", name=op.f("ck_relationships_not_self")
        ),
        sa.CheckConstraint(
            "derivation_method IN ('source', 'inferred', 'manual')",
            name=op.f("ck_relationships_derivation_method"),
        ),
        sa.CheckConstraint(
            "lifecycle_status IN ('active', 'inactive', 'retired')",
            name=op.f("ck_relationships_lifecycle_status"),
        ),
        sa.ForeignKeyConstraint(
            ["subject_id"], ["catalog.objects.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["object_id"], ["catalog.objects.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["provenance_object_source_id"],
            ["catalog.object_sources.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["first_seen_import_run_id"], ["meta.import_runs.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["last_seen_import_run_id"], ["meta.import_runs.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="catalog",
    )
    op.create_index(
        "ix_catalog_relationships_subject_type",
        "relationships",
        ["subject_id", "relationship_type"],
        schema="catalog",
    )
    op.create_index(
        "ix_catalog_relationships_object_type",
        "relationships",
        ["object_id", "relationship_type"],
        schema="catalog",
    )


def downgrade() -> None:
    op.drop_table("relationships", schema="catalog")
    op.drop_constraint(
        "fk_objects_geometry_source_id_object_sources",
        "objects",
        schema="catalog",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_objects_name_source_id_object_sources",
        "objects",
        schema="catalog",
        type_="foreignkey",
    )
    op.drop_table("object_sources", schema="catalog")
    op.drop_table("objects", schema="catalog")
