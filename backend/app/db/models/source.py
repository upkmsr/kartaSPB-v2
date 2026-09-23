from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class DatasetSource(Base):
    __tablename__ = "dataset_sources"
    __table_args__ = {"schema": "meta"}

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    provider: Mapped[str] = mapped_column(String(200))
    source_type: Mapped[str] = mapped_column(String(50))
    source_url: Mapped[str] = mapped_column(Text())
    license: Mapped[str | None] = mapped_column(String(200))
    attribution: Mapped[str | None] = mapped_column(Text())
    version: Mapped[str | None] = mapped_column(String(100))
    checksum: Mapped[str | None] = mapped_column(String(128))
    local_filename: Mapped[str | None] = mapped_column(Text())
    downloaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    import_runs: Mapped[list["ImportRun"]] = relationship(
        back_populates="source", cascade="all, delete-orphan"
    )


from app.db.models.import_run import ImportRun  # noqa: E402
