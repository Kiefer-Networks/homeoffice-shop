from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class OrderCreate(BaseModel):
    delivery_note: str | None = None
    confirm_price_changes: bool = False


class OrderStatusUpdate(BaseModel):
    status: str
    admin_note: str | None = None


class OrderItemResponse(BaseModel):
    id: UUID
    product_id: UUID
    product_name: str | None = None
    quantity: int
    price_cents: int
    external_url: str
    vendor_ordered: bool = False


class OrderResponse(BaseModel):
    id: UUID
    user_id: UUID
    user_email: str | None = None
    user_display_name: str | None = None
    status: str
    total_cents: int
    delivery_note: str | None = None
    admin_note: str | None = None
    reviewed_by: UUID | None = None
    reviewed_at: datetime | None = None
    items: list[OrderItemResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class OrderListResponse(BaseModel):
    items: list[OrderResponse]
    total: int
    page: int
    per_page: int


class OrderItemCheckUpdate(BaseModel):
    vendor_ordered: bool
