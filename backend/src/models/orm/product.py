import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, VARCHAR, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.models.orm.base import Base


class Product(Base):
    __tablename__ = "products"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("categories.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    brand: Mapped[str | None] = mapped_column(String(255), nullable=True)
    model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_gallery: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    specifications: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    price_min_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    price_max_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    color: Mapped[str | None] = mapped_column(VARCHAR(100), nullable=True)
    material: Mapped[str | None] = mapped_column(VARCHAR(255), nullable=True)
    product_dimensions: Mapped[str | None] = mapped_column(VARCHAR(255), nullable=True)
    item_weight: Mapped[str | None] = mapped_column(VARCHAR(100), nullable=True)
    item_model_number: Mapped[str | None] = mapped_column(VARCHAR(100), nullable=True)
    product_information: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    variants: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    amazon_asin: Mapped[str | None] = mapped_column(String(20), nullable=True)
    external_url: Mapped[str] = mapped_column(Text, nullable=False)
    brand_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    max_quantity_per_user: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1
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
