import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.orm.base import Base


class HiBobSyncLog(Base):
    __tablename__ = "hibob_sync_log"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    employees_synced: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    employees_created: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    employees_updated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    employees_deactivated: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
