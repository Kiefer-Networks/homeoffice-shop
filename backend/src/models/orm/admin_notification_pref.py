import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.orm.base import Base

DEFAULT_SLACK_EVENTS = ["order.created", "order.cancelled"]
DEFAULT_EMAIL_EVENTS = ["order.created"]


class AdminNotificationPref(Base):
    __tablename__ = "admin_notification_prefs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), unique=True, nullable=False
    )
    slack_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    slack_events: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list(DEFAULT_SLACK_EVENTS)
    )
    email_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    email_events: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list(DEFAULT_EMAIL_EVENTS)
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
