# ruff: noqa: E501
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from geoalchemy2 import Geometry
from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CatalogObject(Base):
    __tablename__ = "objects"
    __table_args__ = (
        CheckConstraint("object_kind IN ('feature', 'boundary')", name="object_kind"),
        CheckConstraint(
            "lifecycle_status IN ('active', 'inactive', 'merged', 'retired')",
            name="lifecycle_status",
        ),
        CheckConstraint(
            "lifecycle_status <> 'active' OR "
            "(geom IS NOT NULL AND NOT ST_IsEmpty(geom) AND ST_IsValid(geom))",
            name="active_geometry",
        ),
        CheckConstraint(
            "superseded_by IS NULL OR superseded_by <> id",
            name="superseded_by_not_self",
        ),
        CheckConstraint(
            "lifecycle_status <> 'merged' OR superseded_by IS NOT NULL",
            name="merged_has_successor",
        ),
        Index("ix_catalog_objects_geom_gist", "geom", postgresql_using="gist"),
        Index("ix_catalog_objects_kind_status", "object_kind", "lifecycle_status"),
        Index("ix_catalog_objects_properties_gin", "properties", postgresql_using="gin"),
        Index("ix_catalog_objects_superseded_by", "superseded_by"),
        {"schema": "catalog"},
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=text("gen_random_uuid()"),
    )
    object_kind: Mapped[str] = mapped_column(String(24))
    lifecycle_status: Mapped[str] = mapped_column(
        String(16), default="active", server_default="active"
    )
    name: Mapped[str | None] = mapped_column(Text())
    geom: Mapped[Any | None] = mapped_column(Geometry("GEOMETRY", srid=4326, spatial_index=False))
    name_source_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "catalog.object_sources.id",
            name="fk_objects_name_source_id_object_sources",
            ondelete="SET NULL",
            use_alter=True,
        )
    )
    geometry_source_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "catalog.object_sources.id",
            name="fk_objects_geometry_source_id_object_sources",
            ondelete="SET NULL",
            use_alter=True,
        )
    )
    geometry_locked: Mapped[bool] = mapped_column(default=False, server_default=text("false"))
    properties: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), default=dict, server_default="{}"
    )
    property_sources: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), default=dict, server_default="{}"
    )
    revision: Mapped[int] = mapped_column(BigInteger, default=1, server_default="1")
    superseded_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("catalog.objects.id", ondelete="RESTRICT")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ObjectSource(Base):
    __tablename__ = "object_sources"
    __table_args__ = (
        CheckConstraint(
            "source_status IN ('present', 'missing', 'deleted', 'superseded')",
            name="source_status",
        ),
        CheckConstraint(
            "candidate_geom IS NULL OR "
            "(NOT ST_IsEmpty(candidate_geom) AND ST_IsValid(candidate_geom))",
            name="candidate_geometry",
        ),
        CheckConstraint("char_length(payload_hash) = 64", name="payload_hash"),
        CheckConstraint(
            "match_confidence >= 0 AND match_confidence <= 1",
            name="match_confidence",
        ),
        UniqueConstraint(
            "source_id",
            "source_object_type",
            "source_object_id",
            name="uq_object_sources_source_identity",
        ),
        Index("ix_catalog_object_sources_object_status", "object_id", "source_status"),
        Index(
            "ix_catalog_object_sources_candidate_geom_gist",
            "candidate_geom",
            postgresql_using="gist",
        ),
        Index(
            "ix_catalog_object_sources_candidate_properties_gin",
            "candidate_properties",
            postgresql_using="gin",
        ),
        {"schema": "catalog"},
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    object_id: Mapped[UUID] = mapped_column(ForeignKey("catalog.objects.id", ondelete="RESTRICT"))
    source_id: Mapped[int] = mapped_column(
        ForeignKey("meta.dataset_sources.id", ondelete="RESTRICT")
    )
    source_object_type: Mapped[str] = mapped_column(String(32))
    source_object_id: Mapped[str] = mapped_column(Text())
    source_native_version: Mapped[str | None] = mapped_column(Text())
    source_status: Mapped[str] = mapped_column(
        String(16), default="present", server_default="present"
    )
    candidate_name: Mapped[str | None] = mapped_column(Text())
    candidate_geom: Mapped[Any | None] = mapped_column(
        Geometry("GEOMETRY", srid=4326, spatial_index=False)
    )
    candidate_properties: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), default=dict, server_default="{}"
    )
    payload_hash: Mapped[str] = mapped_column(String(64))
    geometry_quality: Mapped[str] = mapped_column(String(24))
    source_priority: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    match_method: Mapped[str] = mapped_column(String(32))
    match_confidence: Mapped[Decimal] = mapped_column(Numeric(4, 3))
    first_seen_import_run_id: Mapped[int] = mapped_column(
        ForeignKey("meta.import_runs.id", ondelete="RESTRICT")
    )
    last_seen_import_run_id: Mapped[int] = mapped_column(
        ForeignKey("meta.import_runs.id", ondelete="RESTRICT")
    )
    last_changed_import_run_id: Mapped[int] = mapped_column(
        ForeignKey("meta.import_runs.id", ondelete="RESTRICT")
    )
    missing_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class CatalogRelationship(Base):
    __tablename__ = "relationships"
    __table_args__ = (
        CheckConstraint("subject_id <> object_id", name="not_self"),
        CheckConstraint(
            "derivation_method IN ('source', 'inferred', 'manual')",
            name="derivation_method",
        ),
        CheckConstraint(
            "lifecycle_status IN ('active', 'inactive', 'retired')",
            name="lifecycle_status",
        ),
        Index("ix_catalog_relationships_subject_type", "subject_id", "relationship_type"),
        Index("ix_catalog_relationships_object_type", "object_id", "relationship_type"),
        {"schema": "catalog"},
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=text("gen_random_uuid()"),
    )
    subject_id: Mapped[UUID] = mapped_column(ForeignKey("catalog.objects.id", ondelete="RESTRICT"))
    relationship_type: Mapped[str] = mapped_column(String(64))
    object_id: Mapped[UUID] = mapped_column(ForeignKey("catalog.objects.id", ondelete="RESTRICT"))
    provenance_object_source_id: Mapped[int | None] = mapped_column(
        ForeignKey("catalog.object_sources.id", ondelete="SET NULL")
    )
    derivation_method: Mapped[str] = mapped_column(String(24))
    lifecycle_status: Mapped[str] = mapped_column(
        String(16), default="active", server_default="active"
    )
    properties: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), default=dict, server_default="{}"
    )
    first_seen_import_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("meta.import_runs.id", ondelete="RESTRICT")
    )
    last_seen_import_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("meta.import_runs.id", ondelete="RESTRICT")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Category(Base):
    __tablename__ = "categories"
    __table_args__ = ({"schema": "catalog"},)

    key: Mapped[str] = mapped_column(String(96), primary_key=True)
    parent_key: Mapped[str | None] = mapped_column(
        ForeignKey("catalog.categories.key", ondelete="RESTRICT")
    )
    label: Mapped[str] = mapped_column(Text())
    enabled: Mapped[bool] = mapped_column(default=True, server_default=text("true"))
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON().with_variant(JSONB(), "postgresql"), default=dict, server_default="{}"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ObjectCategory(Base):
    __tablename__ = "object_categories"
    __table_args__ = (
        CheckConstraint("lifecycle_status IN ('active','inactive')", name="lifecycle_status"),
        Index("ix_catalog_object_categories_category", "category_key"),
        Index("ix_catalog_object_categories_category_status", "category_key", "lifecycle_status"),
        {"schema": "catalog"},
    )

    object_id: Mapped[UUID] = mapped_column(
        ForeignKey("catalog.objects.id", ondelete="CASCADE"), primary_key=True
    )
    category_key: Mapped[str] = mapped_column(
        ForeignKey("catalog.categories.key", ondelete="RESTRICT"), primary_key=True
    )
    lifecycle_status: Mapped[str] = mapped_column(
        String(16), default="active", server_default="active"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ObjectCategorySource(Base):
    __tablename__ = "object_category_sources"
    __table_args__ = (
        CheckConstraint("status IN ('active','inactive')", name="status"),
        Index("ix_catalog_category_sources_object_category", "object_id", "category_key", "status"),
        Index("ix_catalog_category_sources_rule", "rule_id", "rule_version"),
        {"schema": "catalog"},
    )

    object_id: Mapped[UUID] = mapped_column(ForeignKey("catalog.objects.id", ondelete="CASCADE"))
    category_key: Mapped[str] = mapped_column(
        ForeignKey("catalog.categories.key", ondelete="RESTRICT"), primary_key=True
    )
    object_source_id: Mapped[int] = mapped_column(
        ForeignKey("catalog.object_sources.id", ondelete="CASCADE"), primary_key=True
    )
    rule_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    rule_version: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16), default="active", server_default="active")
    evidence: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), default=dict, server_default="{}"
    )
    first_seen_import_run_id: Mapped[int] = mapped_column(
        ForeignKey("meta.import_runs.id", ondelete="RESTRICT")
    )
    last_seen_import_run_id: Mapped[int] = mapped_column(
        ForeignKey("meta.import_runs.id", ondelete="RESTRICT")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
