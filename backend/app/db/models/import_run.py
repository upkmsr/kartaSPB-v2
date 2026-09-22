from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import JSON, BigInteger, CheckConstraint, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ImportRunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class ImportRun(Base):
    __tablename__ = "import_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'running', 'success', 'failed')", name="status_allowed"
        ),
        {"schema": "meta"},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(
        ForeignKey("meta.dataset_sources.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(
        String(20), default=ImportRunStatus.PENDING, server_default=ImportRunStatus.PENDING
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_version: Mapped[str | None] = mapped_column(String(200))
    checksum: Mapped[str | None] = mapped_column(String(128))
    processed_count: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    inserted_count: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    updated_count: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    skipped_count: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    error_count: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    details: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), default=dict, server_default="{}"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    source: Mapped["DatasetSource"] = relationship(back_populates="import_runs")


from app.db.models.source import DatasetSource  # noqa: E402
