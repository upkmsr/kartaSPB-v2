from datetime import datetime
from typing import Any

from geoalchemy2 import Geometry
from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class OsmNode(Base):
    __tablename__ = "osm_nodes"
    __table_args__ = (
        CheckConstraint("osm_type = 'node'", name="osm_type"),
        Index("uq_osm_nodes_identity", "osm_type", "osm_id", "source_id", unique=True),
        Index("ix_osm_nodes_import_run_id", "import_run_id"),
        Index("ix_osm_nodes_geom_gist", "geom", postgresql_using="gist"),
        {"schema": "staging"},
    )

    source_id: Mapped[int] = mapped_column(
        ForeignKey("meta.dataset_sources.id", ondelete="CASCADE"), primary_key=True
    )
    osm_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    osm_type: Mapped[str] = mapped_column(String(8), default="node", server_default="node")
    tags: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), default=dict
    )
    geom: Mapped[Any | None] = mapped_column(
        Geometry("POINT", srid=4326, spatial_index=False), nullable=True
    )
    import_run_id: Mapped[int] = mapped_column(
        ForeignKey("meta.import_runs.id", ondelete="RESTRICT")
    )
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class OsmWay(Base):
    __tablename__ = "osm_ways"
    __table_args__ = (
        CheckConstraint("osm_type = 'way'", name="osm_type"),
        Index("uq_osm_ways_identity", "osm_type", "osm_id", "source_id", unique=True),
        Index("ix_osm_ways_import_run_id", "import_run_id"),
        Index("ix_osm_ways_geom_gist", "geom", postgresql_using="gist"),
        {"schema": "staging"},
    )

    source_id: Mapped[int] = mapped_column(
        ForeignKey("meta.dataset_sources.id", ondelete="CASCADE"), primary_key=True
    )
    osm_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    osm_type: Mapped[str] = mapped_column(String(8), default="way", server_default="way")
    tags: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), default=dict
    )
    geom: Mapped[Any | None] = mapped_column(
        Geometry("GEOMETRY", srid=4326, spatial_index=False), nullable=True
    )
    import_run_id: Mapped[int] = mapped_column(
        ForeignKey("meta.import_runs.id", ondelete="RESTRICT")
    )
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class OsmRelation(Base):
    __tablename__ = "osm_relations"
    __table_args__ = (
        CheckConstraint("osm_type = 'relation'", name="osm_type"),
        Index("uq_osm_relations_identity", "osm_type", "osm_id", "source_id", unique=True),
        Index("ix_osm_relations_import_run_id", "import_run_id"),
        Index("ix_osm_relations_geom_gist", "geom", postgresql_using="gist"),
        {"schema": "staging"},
    )

    source_id: Mapped[int] = mapped_column(
        ForeignKey("meta.dataset_sources.id", ondelete="CASCADE"), primary_key=True
    )
    osm_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    osm_type: Mapped[str] = mapped_column(String(8), default="relation", server_default="relation")
    tags: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), default=dict
    )
    geom: Mapped[Any | None] = mapped_column(
        Geometry("GEOMETRY", srid=4326, spatial_index=False), nullable=True
    )
    import_run_id: Mapped[int] = mapped_column(
        ForeignKey("meta.import_runs.id", ondelete="RESTRICT")
    )
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class OsmRelationMember(Base):
    __tablename__ = "osm_relation_members"
    __table_args__ = (
        CheckConstraint("member_type IN ('node', 'way', 'relation')", name="member_type"),
        ForeignKeyConstraint(
            ["source_id", "relation_id"],
            ["staging.osm_relations.source_id", "staging.osm_relations.osm_id"],
            ondelete="CASCADE",
        ),
        Index("ix_osm_relation_members_member", "member_type", "member_id"),
        Index("ix_osm_relation_members_import_run_id", "import_run_id"),
        {"schema": "staging"},
    )

    source_id: Mapped[int] = mapped_column(primary_key=True)
    relation_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    sequence: Mapped[int] = mapped_column(Integer, primary_key=True)
    member_type: Mapped[str] = mapped_column(String(8))
    member_id: Mapped[int] = mapped_column(BigInteger)
    role: Mapped[str] = mapped_column(Text(), default="", server_default="")
    import_run_id: Mapped[int] = mapped_column(
        ForeignKey("meta.import_runs.id", ondelete="RESTRICT")
    )


class OsmRelationGeometry(Base):
    __tablename__ = "osm_relation_geometries"
    __table_args__ = (
        CheckConstraint(
            "relation_type IN ('multipolygon', 'boundary', 'route')",
            name="relation_type",
        ),
        CheckConstraint("geometry_kind IN ('area', 'route')", name="geometry_kind"),
        CheckConstraint(
            "assembly_status IN "
            "('assembled', 'partial', 'incomplete', 'invalid', 'unsupported_nested')",
            name="assembly_status",
        ),
        CheckConstraint(
            "assembly_status <> 'assembled' OR geom IS NOT NULL",
            name="assembled_geometry_not_null",
        ),
        ForeignKeyConstraint(
            ["source_id", "relation_id"],
            ["staging.osm_relations.source_id", "staging.osm_relations.osm_id"],
            ondelete="CASCADE",
        ),
        Index("ix_osm_relation_geometries_geom_gist", "geom", postgresql_using="gist"),
        Index(
            "ix_osm_relation_geometries_type_status",
            "relation_type",
            "assembly_status",
        ),
        Index("ix_osm_relation_geometries_import_run_id", "import_run_id"),
        {"schema": "derived"},
    )

    source_id: Mapped[int] = mapped_column(primary_key=True)
    relation_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    relation_type: Mapped[str] = mapped_column(String(32))
    geometry_kind: Mapped[str] = mapped_column(String(16))
    assembly_method: Mapped[str] = mapped_column(String(64))
    assembly_status: Mapped[str] = mapped_column(String(32))
    diagnostics: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), default=dict
    )
    geom: Mapped[Any | None] = mapped_column(
        Geometry("GEOMETRY", srid=4326, spatial_index=False), nullable=True
    )
    import_run_id: Mapped[int] = mapped_column(
        ForeignKey("meta.import_runs.id", ondelete="RESTRICT")
    )
    assembled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
