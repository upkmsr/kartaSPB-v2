"""Add OSM source metadata and staging tables.

Revision ID: 20260922_0002
Revises: 20260922_0001
Create Date: 2026-09-22
"""

from collections.abc import Sequence

import geoalchemy2
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260922_0002"
down_revision: str | None = "20260922_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("dataset_sources", sa.Column("version", sa.String(100)), schema="meta")
    op.add_column("dataset_sources", sa.Column("checksum", sa.String(128)), schema="meta")
    op.add_column("dataset_sources", sa.Column("local_filename", sa.Text()), schema="meta")
    op.add_column(
        "dataset_sources", sa.Column("downloaded_at", sa.DateTime(timezone=True)), schema="meta"
    )
    op.add_column(
        "dataset_sources",
        sa.Column("source_updated_at", sa.DateTime(timezone=True)),
        schema="meta",
    )

    table_specs = (
        ("osm_nodes", "node", "POINT"),
        ("osm_ways", "way", "GEOMETRY"),
        ("osm_relations", "relation", "GEOMETRY"),
    )
    for table_name, osm_type, geometry_type in table_specs:
        op.create_table(
            table_name,
            sa.Column("source_id", sa.Integer(), nullable=False),
            sa.Column("osm_id", sa.BigInteger(), nullable=False),
            sa.Column("osm_type", sa.String(8), server_default=osm_type, nullable=False),
            sa.Column(
                "tags",
                postgresql.JSONB(astext_type=sa.Text()),
                server_default=sa.text("'{}'::jsonb"),
                nullable=False,
            ),
            sa.Column(
                "geom",
                geoalchemy2.types.Geometry(
                    geometry_type=geometry_type,
                    srid=4326,
                    spatial_index=False,
                ),
                nullable=True,
            ),
            sa.Column("import_run_id", sa.Integer(), nullable=False),
            sa.Column(
                "imported_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.CheckConstraint(
                f"osm_type = '{osm_type}'", name=op.f(f"ck_{table_name}_osm_type")
            ),
            sa.ForeignKeyConstraint(
                ["source_id"], ["meta.dataset_sources.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(
                ["import_run_id"], ["meta.import_runs.id"], ondelete="RESTRICT"
            ),
            sa.PrimaryKeyConstraint("source_id", "osm_id"),
            schema="staging",
        )
        op.create_index(
            f"uq_{table_name}_identity",
            table_name,
            ["osm_type", "osm_id", "source_id"],
            unique=True,
            schema="staging",
        )
        op.create_index(
            f"ix_{table_name}_geom_gist",
            table_name,
            ["geom"],
            postgresql_using="gist",
            schema="staging",
        )
        op.create_index(
            f"ix_{table_name}_import_run_id",
            table_name,
            ["import_run_id"],
            schema="staging",
        )

    op.create_table(
        "osm_relation_members",
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("relation_id", sa.BigInteger(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("member_type", sa.String(8), nullable=False),
        sa.Column("member_id", sa.BigInteger(), nullable=False),
        sa.Column("role", sa.Text(), server_default="", nullable=False),
        sa.Column("import_run_id", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "member_type IN ('node', 'way', 'relation')",
            name=op.f("ck_osm_relation_members_member_type"),
        ),
        sa.ForeignKeyConstraint(
            ["source_id", "relation_id"],
            ["staging.osm_relations.source_id", "staging.osm_relations.osm_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["import_run_id"], ["meta.import_runs.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("source_id", "relation_id", "sequence"),
        schema="staging",
    )
    op.create_index(
        "ix_osm_relation_members_member",
        "osm_relation_members",
        ["member_type", "member_id"],
        schema="staging",
    )
    op.create_index(
        "ix_osm_relation_members_import_run_id",
        "osm_relation_members",
        ["import_run_id"],
        schema="staging",
    )


def downgrade() -> None:
    op.drop_table("osm_relation_members", schema="staging")
    op.drop_table("osm_relations", schema="staging")
    op.drop_table("osm_ways", schema="staging")
    op.drop_table("osm_nodes", schema="staging")
    for column in (
        "source_updated_at",
        "downloaded_at",
        "local_filename",
        "checksum",
        "version",
    ):
        op.drop_column("dataset_sources", column, schema="meta")
