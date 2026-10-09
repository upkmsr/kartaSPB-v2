from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from geoalchemy2 import Geometry
from sqlalchemy import (
    CHAR,
    JSON,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
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
        Index(
            "ix_analytics_analysis_cells_grid_district_cell",
            "grid_version",
            "district_id",
            "cell_id",
        ),
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


class MetricRun(Base):
    __tablename__ = "metric_runs"
    __table_args__ = (
        CheckConstraint("btrim(metric_key) <> ''", name="metric_key_not_blank"),
        CheckConstraint("btrim(grid_version) <> ''", name="grid_version_not_blank"),
        CheckConstraint("cell_count > 0", name="cell_count_positive"),
        CheckConstraint(
            "definition_checksum ~ '^[0-9a-f]{64}$'", name="definition_checksum"
        ),
        CheckConstraint(
            "input_fingerprint ~ '^[0-9a-f]{64}$'", name="input_fingerprint"
        ),
        CheckConstraint("run_signature ~ '^[0-9a-f]{64}$'", name="run_signature"),
        CheckConstraint("values_checksum ~ '^[0-9a-f]{64}$'", name="values_checksum"),
        UniqueConstraint("run_signature"),
        Index("ix_analytics_metric_runs_metric_grid", "metric_key", "grid_version"),
        {"schema": "analytics"},
    )

    run_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=text("gen_random_uuid()"),
    )
    metric_key: Mapped[str] = mapped_column(String(200))
    definition_version: Mapped[str] = mapped_column(String(100))
    calculation_version: Mapped[str] = mapped_column(String(100))
    grid_version: Mapped[str] = mapped_column(String(100))
    definition_checksum: Mapped[str] = mapped_column(CHAR(64))
    input_fingerprint: Mapped[str] = mapped_column(CHAR(64))
    definition_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql")
    )
    run_signature: Mapped[str] = mapped_column(CHAR(64))
    cell_count: Mapped[int] = mapped_column(Integer())
    min_value: Mapped[float] = mapped_column(Float())
    max_value: Mapped[float] = mapped_column(Float())
    mean_value: Mapped[float] = mapped_column(Float())
    values_checksum: Mapped[str] = mapped_column(CHAR(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class CellMetricValue(Base):
    __tablename__ = "cell_metric_values"
    __table_args__ = (
        CheckConstraint(
            "raw_value = raw_value AND raw_value NOT IN "
            "('Infinity'::double precision, '-Infinity'::double precision)",
            name="raw_value_finite",
        ),
        Index("ix_analytics_cell_metric_values_cell_id", "cell_id"),
        {"schema": "analytics"},
    )

    run_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("analytics.metric_runs.run_id", ondelete="RESTRICT"),
        primary_key=True,
    )
    cell_id: Mapped[str] = mapped_column(
        ForeignKey("analytics.analysis_cells.cell_id", ondelete="RESTRICT"),
        primary_key=True,
    )
    raw_value: Mapped[float] = mapped_column(Float())


class MetricCurrentRun(Base):
    __tablename__ = "metric_current_runs"
    __table_args__ = ({"schema": "analytics"},)

    metric_key: Mapped[str] = mapped_column(String(200), primary_key=True)
    grid_version: Mapped[str] = mapped_column(String(100), primary_key=True)
    run_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("analytics.metric_runs.run_id", ondelete="RESTRICT"),
        unique=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class MetricScoreRun(Base):
    __tablename__ = "metric_score_runs"
    __table_args__ = (
        CheckConstraint("btrim(metric_key) <> ''", name="metric_key_not_blank"),
        CheckConstraint("btrim(grid_version) <> ''", name="grid_version_not_blank"),
        CheckConstraint("cell_count > 0", name="cell_count_positive"),
        CheckConstraint(
            "normalization_checksum ~ '^[0-9a-f]{64}$'", name="normalization_checksum"
        ),
        CheckConstraint("run_signature ~ '^[0-9a-f]{64}$'", name="run_signature"),
        CheckConstraint("values_checksum ~ '^[0-9a-f]{64}$'", name="values_checksum"),
        CheckConstraint("score_min >= 0", name="score_min_nonnegative"),
        CheckConstraint("score_max <= 100", name="score_max_at_most_100"),
        CheckConstraint("score_min <= score_mean", name="score_min_le_mean"),
        CheckConstraint("score_mean <= score_max", name="score_mean_le_max"),
        UniqueConstraint("run_signature"),
        Index(
            "ix_analytics_metric_score_runs_metric_grid", "metric_key", "grid_version"
        ),
        {"schema": "analytics"},
    )

    score_run_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=text("gen_random_uuid()"),
    )
    metric_key: Mapped[str] = mapped_column(String(200))
    grid_version: Mapped[str] = mapped_column(String(100))
    metric_run_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("analytics.metric_runs.run_id", ondelete="RESTRICT"),
    )
    normalization_version: Mapped[str] = mapped_column(String(100))
    normalization_checksum: Mapped[str] = mapped_column(CHAR(64))
    normalization_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql")
    )
    run_signature: Mapped[str] = mapped_column(CHAR(64))
    cell_count: Mapped[int] = mapped_column(Integer())
    score_min: Mapped[float] = mapped_column(Float())
    score_max: Mapped[float] = mapped_column(Float())
    score_mean: Mapped[float] = mapped_column(Float())
    values_checksum: Mapped[str] = mapped_column(CHAR(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class CellMetricScore(Base):
    __tablename__ = "cell_metric_scores"
    __table_args__ = (
        CheckConstraint(
            "score = score AND score NOT IN "
            "('Infinity'::double precision, '-Infinity'::double precision)",
            name="score_finite",
        ),
        CheckConstraint("score >= 0 AND score <= 100", name="score_in_range"),
        Index("ix_analytics_cell_metric_scores_cell_id", "cell_id"),
        {"schema": "analytics"},
    )

    score_run_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("analytics.metric_score_runs.score_run_id", ondelete="RESTRICT"),
        primary_key=True,
    )
    cell_id: Mapped[str] = mapped_column(
        ForeignKey("analytics.analysis_cells.cell_id", ondelete="RESTRICT"),
        primary_key=True,
    )
    score: Mapped[float] = mapped_column(Float())


class MetricScoreCurrentRun(Base):
    __tablename__ = "metric_score_current_runs"
    __table_args__ = (UniqueConstraint("score_run_id"), {"schema": "analytics"})

    metric_key: Mapped[str] = mapped_column(String(200), primary_key=True)
    grid_version: Mapped[str] = mapped_column(String(100), primary_key=True)
    score_run_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("analytics.metric_score_runs.score_run_id", ondelete="RESTRICT"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
