import uuid
from datetime import date, datetime

from sqlalchemy import BigInteger, Boolean, Date, DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.orm.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    hibob_id: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    department: Mapped[str | None] = mapped_column(String(255), nullable=True)
    manager_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    manager_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    total_budget_cents: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    cached_spent_cents: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    cached_adjustment_cents: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0
    )
    budget_cache_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    probation_override: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    provider_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[str] = mapped_column(String(50), nullable=False, default="employee")
    avatar_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    last_hibob_sync: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
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
