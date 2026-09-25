from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, SmallInteger, Text, func, text
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
