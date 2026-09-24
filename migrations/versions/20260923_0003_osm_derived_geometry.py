"""Add the derived OSM relation geometry layer.

Revision ID: 20260923_0003
Revises: 20260922_0002
Create Date: 2026-09-23
"""

from collections.abc import Sequence

import geoalchemy2
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260923_0003"
down_revision: str | None = "20260922_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute('CREATE SCHEMA IF NOT EXISTS "derived"')
    op.create_table(
        "osm_relation_geometries",
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("relation_id", sa.BigInteger(), nullable=False),
        sa.Column("relation_type", sa.String(32), nullable=False),
        sa.Column("geometry_kind", sa.String(16), nullable=False),
        sa.Column("assembly_method", sa.String(64), nullable=False),
        sa.Column("assembly_status", sa.String(32), nullable=False),
        sa.Column(
            "diagnostics",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "geom",
            geoalchemy2.types.Geometry(
                geometry_type="GEOMETRY",
                srid=4326,
                spatial_index=False,
            ),
            nullable=True,
        ),
        sa.Column("import_run_id", sa.Integer(), nullable=False),
        sa.Column(
            "assembled_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "relation_type IN ('multipolygon', 'boundary', 'route')",
            name=op.f("ck_osm_relation_geometries_relation_type"),
        ),
        sa.CheckConstraint(
            "geometry_kind IN ('area', 'route')",
            name=op.f("ck_osm_relation_geometries_geometry_kind"),
        ),
        sa.CheckConstraint(
            "assembly_status IN "
            "('assembled', 'partial', 'incomplete', 'invalid', 'unsupported_nested')",
            name=op.f("ck_osm_relation_geometries_assembly_status"),
        ),
        sa.CheckConstraint(
            "assembly_status <> 'assembled' OR geom IS NOT NULL",
            name=op.f("ck_osm_relation_geometries_assembled_geometry_not_null"),
        ),
        sa.ForeignKeyConstraint(
            ["source_id", "relation_id"],
            ["staging.osm_relations.source_id", "staging.osm_relations.osm_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["import_run_id"], ["meta.import_runs.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("source_id", "relation_id"),
        schema="derived",
    )
    op.create_index(
        "ix_osm_relation_geometries_geom_gist",
        "osm_relation_geometries",
        ["geom"],
        postgresql_using="gist",
        schema="derived",
    )
    op.create_index(
        "ix_osm_relation_geometries_type_status",
        "osm_relation_geometries",
        ["relation_type", "assembly_status"],
        schema="derived",
    )
    op.create_index(
        "ix_osm_relation_geometries_import_run_id",
        "osm_relation_geometries",
        ["import_run_id"],
        schema="derived",
    )

    op.execute(
        """
        CREATE VIEW derived.osm_route_members AS
        SELECT
            members.source_id,
            members.relation_id,
            members.sequence,
            members.member_type,
            members.member_id,
            members.role,
            CASE
                WHEN members.role LIKE 'stop%' THEN 'stop_position'
                WHEN members.role LIKE 'platform%' THEN 'platform'
                WHEN members.member_type = 'way' THEN 'path'
                WHEN members.member_type = 'relation' THEN 'relation'
                ELSE 'other'
            END AS member_kind,
            CASE members.member_type
                WHEN 'node' THEN nodes.tags
                WHEN 'way' THEN ways.tags
                WHEN 'relation' THEN child_relations.tags
            END AS member_tags,
            CASE members.member_type
                WHEN 'node' THEN nodes.geom
                WHEN 'way' THEN ways.geom
                WHEN 'relation' THEN child_geometries.geom
            END AS member_geom,
            CASE members.member_type
                WHEN 'node' THEN nodes.osm_id IS NOT NULL
                WHEN 'way' THEN ways.osm_id IS NOT NULL
                WHEN 'relation' THEN child_relations.osm_id IS NOT NULL
                ELSE false
            END AS is_resolved
        FROM staging.osm_relation_members AS members
        JOIN staging.osm_relations AS routes
          ON routes.source_id = members.source_id
         AND routes.osm_id = members.relation_id
         AND routes.tags ->> 'type' = 'route'
        LEFT JOIN staging.osm_nodes AS nodes
          ON members.member_type = 'node'
         AND nodes.source_id = members.source_id
         AND nodes.osm_id = members.member_id
        LEFT JOIN staging.osm_ways AS ways
          ON members.member_type = 'way'
         AND ways.source_id = members.source_id
         AND ways.osm_id = members.member_id
        LEFT JOIN staging.osm_relations AS child_relations
          ON members.member_type = 'relation'
         AND child_relations.source_id = members.source_id
         AND child_relations.osm_id = members.member_id
        LEFT JOIN derived.osm_relation_geometries AS child_geometries
          ON members.member_type = 'relation'
         AND child_geometries.source_id = members.source_id
         AND child_geometries.relation_id = members.member_id
        """
    )
    op.execute(
        """
        CREATE VIEW derived.osm_route_variants AS
        SELECT
            members.source_id,
            members.relation_id AS route_master_id,
            members.sequence,
            members.member_id AS route_relation_id,
            members.role,
            masters.tags ->> 'route_master' AS transport_mode,
            masters.tags ->> 'ref' AS master_ref,
            masters.tags ->> 'name' AS master_name,
            routes.tags ->> 'route' AS route_mode,
            routes.tags ->> 'ref' AS route_ref,
            routes.tags ->> 'name' AS route_name,
            routes.tags ->> 'from' AS route_from,
            routes.tags ->> 'to' AS route_to,
            routes.osm_id IS NOT NULL AS is_resolved
        FROM staging.osm_relation_members AS members
        JOIN staging.osm_relations AS masters
          ON masters.source_id = members.source_id
         AND masters.osm_id = members.relation_id
         AND masters.tags ->> 'type' = 'route_master'
        LEFT JOIN staging.osm_relations AS routes
          ON members.member_type = 'relation'
         AND routes.source_id = members.source_id
         AND routes.osm_id = members.member_id
         AND routes.tags ->> 'type' = 'route'
        WHERE members.member_type = 'relation'
        """
    )


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS derived.osm_route_variants")
    op.execute("DROP VIEW IF EXISTS derived.osm_route_members")
    op.drop_table("osm_relation_geometries", schema="derived")
    op.execute('DROP SCHEMA IF EXISTS "derived"')
