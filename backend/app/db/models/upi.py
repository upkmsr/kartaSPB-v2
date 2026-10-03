from datetime import datetime
from typing import Any

from geoalchemy2 import Geometry
from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UpiSourceProfile(Base):
    __tablename__ = "source_profiles"
    __table_args__ = (
        CheckConstraint(
            "terms_status IN ('TERMS_CLEAR','PUBLIC_BUT_TERMS_UNCLEAR','RESTRICTED','UNKNOWN')",
            name="terms_status_allowed",
        ),
        CheckConstraint(
            "raw_retention_mode IN "
            "('FULL_RAW_ALLOWED','METADATA_ONLY','SAMPLE_ONLY','RETENTION_BLOCKED')",
            name="raw_retention_mode_allowed",
        ),
        {"schema": "upi"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("meta.dataset_sources.id", ondelete="RESTRICT"), unique=True
    )
    source_key: Mapped[str] = mapped_column(String(100), unique=True)
    adapter_key: Mapped[str] = mapped_column(String(100))
    adapter_version: Mapped[str] = mapped_column(String(100))
    normalization_version: Mapped[str] = mapped_column(String(100))
    config_version: Mapped[str] = mapped_column(String(100))
    official_status: Mapped[str] = mapped_column(String(50))
    provenance_kind: Mapped[str] = mapped_column(String(50))
    automation_level: Mapped[str] = mapped_column(String(20))
    service_type: Mapped[str] = mapped_column(String(50))
    primary_url: Mapped[str] = mapped_column(Text())
    service_url: Mapped[str] = mapped_column(Text())
    access_mode: Mapped[str] = mapped_column(String(50))
    terms_status: Mapped[str] = mapped_column(String(50))
    raw_retention_mode: Mapped[str] = mapped_column(String(50))
    retention_policy: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), default=dict, server_default="{}"
    )
    refresh_mode: Mapped[str] = mapped_column(String(50))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class UpiSourceSnapshot(Base):
    __tablename__ = "source_snapshots"
    __table_args__ = (
        CheckConstraint(
            "snapshot_status IN ('COMPLETE','UNCHANGED')", name="snapshot_status_allowed"
        ),
        Index("ix_upi_snapshots_source_created", "source_id", "created_at"),
        {"schema": "upi"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("meta.dataset_sources.id", ondelete="RESTRICT")
    )
    import_run_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("meta.import_runs.id", ondelete="RESTRICT"), unique=True
    )
    previous_snapshot_id: Mapped[int | None] = mapped_column(
        ForeignKey("upi.source_snapshots.id", ondelete="RESTRICT")
    )
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    adapter_version: Mapped[str] = mapped_column(String(100))
    normalization_version: Mapped[str] = mapped_column(String(100))
    config_version: Mapped[str] = mapped_column(String(100))
    request_url: Mapped[str] = mapped_column(Text())
    request_parameters: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), default=dict, server_default="{}"
    )
    http_status: Mapped[int | None] = mapped_column(Integer)
    content_type: Mapped[str | None] = mapped_column(String(255))
    response_headers: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), default=dict, server_default="{}"
    )
    source_crs: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), default=dict, server_default="{}"
    )
    source_version: Mapped[str | None] = mapped_column(String(200))
    source_edit_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    record_count: Mapped[int] = mapped_column(BigInteger)
    schema_fingerprint: Mapped[str] = mapped_column(String(64))
    payload_checksum: Mapped[str] = mapped_column(String(64))
    snapshot_status: Mapped[str] = mapped_column(String(20))
    raw_payload: Mapped[dict[str, Any] | None] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql")
    )
    raw_evidence_locator: Mapped[str | None] = mapped_column(Text())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UpiNormalizedFeature(Base):
    __tablename__ = "normalized_features"
    __table_args__ = (
        UniqueConstraint("snapshot_id", "source_object_id"),
        Index("ix_upi_features_source_object", "source_id", "source_object_id"),
        Index("ix_upi_features_snapshot", "snapshot_id"),
        Index("ix_upi_features_geom_gist", "geom", postgresql_using="gist"),
        {"schema": "upi"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("meta.dataset_sources.id", ondelete="RESTRICT")
    )
    snapshot_id: Mapped[int] = mapped_column(
        ForeignKey("upi.source_snapshots.id", ondelete="RESTRICT")
    )
    source_object_id: Mapped[str] = mapped_column(String(255))
    source_version: Mapped[str | None] = mapped_column(String(200))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    effective_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str | None] = mapped_column(String(255))
    normalization_version: Mapped[str] = mapped_column(String(100))
    properties: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), default=dict, server_default="{}"
    )
    raw_locator: Mapped[str | None] = mapped_column(Text())
    payload_hash: Mapped[str] = mapped_column(String(64))
    geom: Mapped[Any] = mapped_column(Geometry("GEOMETRY", srid=4326, spatial_index=False))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UpiSourceHealth(Base):
    __tablename__ = "source_health"
    __table_args__ = (
        CheckConstraint(
            "status IN ('CURRENT','STALE','SOURCE_UNAVAILABLE','IMPORT_FAILED',"
            "'SCHEMA_CHANGED','PARTIALLY_UPDATED')",
            name="status_allowed",
        ),
        Index("ix_upi_health_source_checked", "source_id", "checked_at"),
        {"schema": "upi"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("meta.dataset_sources.id", ondelete="RESTRICT")
    )
    import_run_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("meta.import_runs.id", ondelete="RESTRICT")
    )
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(40))
    http_status: Mapped[int | None] = mapped_column(Integer)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    schema_fingerprint: Mapped[str | None] = mapped_column(String(64))
    record_count: Mapped[int | None] = mapped_column(BigInteger)
    source_edit_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(100))
    error_message: Mapped[str | None] = mapped_column(Text())
    details: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), default=dict, server_default="{}"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
