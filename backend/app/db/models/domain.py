from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class District(Base):
    __tablename__ = "districts"
    __table_args__ = ({"schema": "domain"},)

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True)
    canonical_object_id: Mapped[UUID] = mapped_column(
        ForeignKey("catalog.objects.id", ondelete="RESTRICT"), unique=True
    )
    name: Mapped[str] = mapped_column(Text())
    slug: Mapped[str] = mapped_column(Text(), unique=True)
    display_order: Mapped[int] = mapped_column(SmallInteger(), unique=True)
    enabled: Mapped[bool] = mapped_column(default=True, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class FacilityEntity(Base):
    __tablename__ = "facility_entities"
    __table_args__ = (
        CheckConstraint(
            "lifecycle_status IN ('active','inactive')", name="lifecycle_status"
        ),
        CheckConstraint(
            "lifecycle_status <> 'active' OR "
            "(representative_object_id IS NOT NULL AND display_object_id IS NOT NULL "
            "AND analysis_object_id IS NOT NULL)",
            name="active_roles",
        ),
        Index("ix_domain_facility_entities_category_status", "category_key", "lifecycle_status"),
        Index("ix_domain_facility_entities_display", "display_object_id"),
        {"schema": "domain"},
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=text("gen_random_uuid()"),
    )
    category_key: Mapped[str] = mapped_column(
        ForeignKey("catalog.categories.key", ondelete="RESTRICT")
    )
    representative_object_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("catalog.objects.id", ondelete="RESTRICT")
    )
    display_object_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("catalog.objects.id", ondelete="RESTRICT")
    )
    analysis_object_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("catalog.objects.id", ondelete="RESTRICT")
    )
    lifecycle_status: Mapped[str] = mapped_column(
        String(16), default="active", server_default="active"
    )
    link_method: Mapped[str] = mapped_column(String(255))
    evidence: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), default=dict, server_default="{}"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class FacilityEntityMember(Base):
    __tablename__ = "facility_entity_members"
    __table_args__ = (
        CheckConstraint(
            "geometry_role IN "
            "('POINT','FACILITY_SITE','BUILDING','OTHER_AREA','UNKNOWN')",
            name="geometry_role",
        ),
        CheckConstraint(
            "lifecycle_status IN ('active','inactive')", name="lifecycle_status"
        ),
        Index(
            "ix_domain_facility_members_object_status",
            "canonical_object_id",
            "lifecycle_status",
        ),
        Index(
            "uq_domain_facility_members_active_object",
            "canonical_object_id",
            unique=True,
            postgresql_where=text("lifecycle_status = 'active'"),
        ),
        {"schema": "domain"},
    )

    facility_entity_id: Mapped[UUID] = mapped_column(
        ForeignKey("domain.facility_entities.id", ondelete="CASCADE"), primary_key=True
    )
    canonical_object_id: Mapped[UUID] = mapped_column(
        ForeignKey("catalog.objects.id", ondelete="RESTRICT"), primary_key=True
    )
    geometry_role: Mapped[str] = mapped_column(String(24))
    lifecycle_status: Mapped[str] = mapped_column(
        String(16), default="active", server_default="active"
    )
    link_method: Mapped[str] = mapped_column(String(255))
    evidence: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), default=dict, server_default="{}"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
