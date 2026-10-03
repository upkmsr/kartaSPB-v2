"""Add the UPI evidence source foundation.

Revision ID: 20261003_0011
Revises: 20261001_0010
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geometry
from sqlalchemy.dialects import postgresql

revision: str = "20261003_0011"
down_revision: str | None = "20261001_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA upi")

    op.create_table(
        "source_profiles",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("source_key", sa.String(length=100), nullable=False),
        sa.Column("adapter_key", sa.String(length=100), nullable=False),
        sa.Column("adapter_version", sa.String(length=100), nullable=False),
        sa.Column("normalization_version", sa.String(length=100), nullable=False),
        sa.Column("config_version", sa.String(length=100), nullable=False),
        sa.Column("official_status", sa.String(length=50), nullable=False),
        sa.Column("provenance_kind", sa.String(length=50), nullable=False),
        sa.Column("automation_level", sa.String(length=20), nullable=False),
        sa.Column("service_type", sa.String(length=50), nullable=False),
        sa.Column("primary_url", sa.Text(), nullable=False),
        sa.Column("service_url", sa.Text(), nullable=False),
        sa.Column("access_mode", sa.String(length=50), nullable=False),
        sa.Column("terms_status", sa.String(length=50), nullable=False),
        sa.Column("raw_retention_mode", sa.String(length=50), nullable=False),
        sa.Column(
            "retention_policy",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("refresh_mode", sa.String(length=50), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "terms_status IN ('TERMS_CLEAR','PUBLIC_BUT_TERMS_UNCLEAR','RESTRICTED','UNKNOWN')",
            name=op.f("ck_source_profiles_terms_status_allowed"),
        ),
        sa.CheckConstraint(
            "raw_retention_mode IN "
            "('FULL_RAW_ALLOWED','METADATA_ONLY','SAMPLE_ONLY','RETENTION_BLOCKED')",
            name=op.f("ck_source_profiles_raw_retention_mode_allowed"),
        ),
        sa.ForeignKeyConstraint(
            ["source_id"], ["meta.dataset_sources.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_id"),
        sa.UniqueConstraint("source_key"),
        schema="upi",
    )

    op.create_table(
        "source_snapshots",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("import_run_id", sa.Integer(), nullable=False),
        sa.Column("previous_snapshot_id", sa.BigInteger(), nullable=True),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("adapter_version", sa.String(length=100), nullable=False),
        sa.Column("normalization_version", sa.String(length=100), nullable=False),
        sa.Column("config_version", sa.String(length=100), nullable=False),
        sa.Column("request_url", sa.Text(), nullable=False),
        sa.Column(
            "request_parameters",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("content_type", sa.String(length=255), nullable=True),
        sa.Column(
            "response_headers",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "source_crs",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("source_version", sa.String(length=200), nullable=True),
        sa.Column("source_edit_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("record_count", sa.BigInteger(), nullable=False),
        sa.Column("schema_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("payload_checksum", sa.String(length=64), nullable=False),
        sa.Column("snapshot_status", sa.String(length=20), nullable=False),
        sa.Column("raw_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("raw_evidence_locator", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "snapshot_status IN ('COMPLETE','UNCHANGED')",
            name=op.f("ck_source_snapshots_snapshot_status_allowed"),
        ),
        sa.ForeignKeyConstraint(
            ["import_run_id"], ["meta.import_runs.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["previous_snapshot_id"], ["upi.source_snapshots.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["source_id"], ["meta.dataset_sources.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("import_run_id"),
        schema="upi",
    )
    op.create_index(
        "ix_upi_snapshots_source_created",
        "source_snapshots",
        ["source_id", "created_at"],
        schema="upi",
    )

    op.create_table(
        "normalized_features",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("snapshot_id", sa.BigInteger(), nullable=False),
        sa.Column("source_object_id", sa.String(length=255), nullable=False),
        sa.Column("source_version", sa.String(length=200), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("effective_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=255), nullable=True),
        sa.Column("normalization_version", sa.String(length=100), nullable=False),
        sa.Column(
            "properties",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("raw_locator", sa.Text(), nullable=True),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "geom", Geometry("GEOMETRY", srid=4326, spatial_index=False), nullable=False
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"], ["upi.source_snapshots.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["source_id"], ["meta.dataset_sources.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("snapshot_id", "source_object_id"),
        schema="upi",
    )
    op.create_index(
        "ix_upi_features_source_object",
        "normalized_features",
        ["source_id", "source_object_id"],
        schema="upi",
    )
    op.create_index(
        "ix_upi_features_snapshot", "normalized_features", ["snapshot_id"], schema="upi"
    )
    op.create_index(
        "ix_upi_features_geom_gist",
        "normalized_features",
        ["geom"],
        schema="upi",
        postgresql_using="gist",
    )

    op.create_table(
        "source_health",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("import_run_id", sa.Integer(), nullable=True),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("schema_fingerprint", sa.String(length=64), nullable=True),
        sa.Column("record_count", sa.BigInteger(), nullable=True),
        sa.Column("source_edit_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "details",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('CURRENT','STALE','SOURCE_UNAVAILABLE','IMPORT_FAILED',"
            "'SCHEMA_CHANGED','PARTIALLY_UPDATED')",
            name=op.f("ck_source_health_status_allowed"),
        ),
        sa.ForeignKeyConstraint(
            ["import_run_id"], ["meta.import_runs.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["source_id"], ["meta.dataset_sources.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="upi",
    )
    op.create_index(
        "ix_upi_health_source_checked",
        "source_health",
        ["source_id", "checked_at"],
        schema="upi",
    )

    op.execute(
        """
        CREATE FUNCTION upi.reject_append_only_mutation() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION '% is append-only', TG_TABLE_SCHEMA || '.' || TG_TABLE_NAME;
        END;
        $$
        """
    )
    for table_name in ("source_snapshots", "normalized_features", "source_health"):
        op.execute(
            f"CREATE TRIGGER trg_{table_name}_append_only "
            f"BEFORE UPDATE OR DELETE ON upi.{table_name} "
            "FOR EACH ROW EXECUTE FUNCTION upi.reject_append_only_mutation()"
        )


def downgrade() -> None:
    for table_name in ("source_health", "normalized_features", "source_snapshots"):
        op.execute(f"DROP TRIGGER trg_{table_name}_append_only ON upi.{table_name}")
    op.execute("DROP FUNCTION upi.reject_append_only_mutation()")
    op.drop_index("ix_upi_health_source_checked", table_name="source_health", schema="upi")
    op.drop_table("source_health", schema="upi")
    op.drop_index("ix_upi_features_geom_gist", table_name="normalized_features", schema="upi")
    op.drop_index("ix_upi_features_snapshot", table_name="normalized_features", schema="upi")
    op.drop_index(
        "ix_upi_features_source_object", table_name="normalized_features", schema="upi"
    )
    op.drop_table("normalized_features", schema="upi")
    op.drop_index("ix_upi_snapshots_source_created", table_name="source_snapshots", schema="upi")
    op.drop_table("source_snapshots", schema="upi")
    op.drop_table("source_profiles", schema="upi")
    op.execute("DROP SCHEMA upi")
