from datetime import datetime
from typing import Any
from uuid import UUID

from geoalchemy2 import Geometry
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AnalysisCell(Base):
    __tablename__ = "analysis_cells"
    __table_args__ = (
        CheckConstraint("btrim(cell_id) <> ''", name="cell_id_not_blank"),
        CheckConstraint("btrim(grid_version) <> ''", name="grid_version_not_blank"),
        CheckConstraint("cell_size_m > 0", name="cell_size_positive"),
        UniqueConstraint("grid_version", "grid_i", "grid_j"),
        Index("ix_analytics_analysis_cells_geom_gist", "geom", postgresql_using="gist"),
        Index(
            "ix_analytics_analysis_cells_center_metric_gist",
            "center_metric",
            postgresql_using="gist",
        ),
        Index("ix_analytics_analysis_cells_grid_version", "grid_version"),
        Index("ix_analytics_analysis_cells_district_id", "district_id"),
        {"schema": "analytics"},
    )

    cell_id: Mapped[str] = mapped_column(String(160), primary_key=True)
    grid_version: Mapped[str] = mapped_column(String(100))
    grid_i: Mapped[int] = mapped_column(Integer())
    grid_j: Mapped[int] = mapped_column(Integer())
    cell_size_m: Mapped[int] = mapped_column(Integer())
    district_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("domain.districts.id", ondelete="RESTRICT"),
    )
    center: Mapped[Any] = mapped_column(
        Geometry("POINT", srid=4326, spatial_index=False)
    )
    center_metric: Mapped[Any] = mapped_column(
        Geometry("POINT", srid=32636, spatial_index=False)
    )
    geom: Mapped[Any] = mapped_column(
        Geometry("POLYGON", srid=4326, spatial_index=False)
    )
    geom_metric: Mapped[Any] = mapped_column(
        Geometry("POLYGON", srid=32636, spatial_index=False)
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
