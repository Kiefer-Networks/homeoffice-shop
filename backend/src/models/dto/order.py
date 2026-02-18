from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class OrderCreate(BaseModel):
    delivery_note: str | None = Field(default=None, max_length=2000)
    confirm_price_changes: bool = False


class OrderStatusUpdate(BaseModel):
    status: Literal["ordered", "delivered", "rejected", "cancelled"]
    admin_note: str | None = Field(default=None, max_length=2000)
    expected_delivery: str | None = Field(default=None, max_length=255)
    purchase_url: str | None = Field(default=None, max_length=2048)


class OrderCancelRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=1000)


class OrderPurchaseUrlUpdate(BaseModel):
    purchase_url: str | None = Field(default=None, max_length=2048)


class OrderItemResponse(BaseModel):
    id: UUID
    product_id: UUID
    product_name: str | None = None
    quantity: int
    price_cents: int
    external_url: str
    vendor_ordered: bool = False
    variant_asin: str | None = None
    variant_value: str | None = None


class OrderInvoiceResponse(BaseModel):
    id: UUID
    filename: str
    uploaded_by: UUID
    uploaded_at: datetime

    model_config = {"from_attributes": True}


class OrderResponse(BaseModel):
    id: UUID
    user_id: UUID
    user_email: str | None = None
    user_display_name: str | None = None
    status: str
    total_cents: int
    delivery_note: str | None = None
    admin_note: str | None = None
    expected_delivery: str | None = None
    purchase_url: str | None = None
    reviewed_by: UUID | None = None
    reviewed_at: datetime | None = None
    cancellation_reason: str | None = None
    cancelled_by: UUID | None = None
    cancelled_at: datetime | None = None
    items: list[OrderItemResponse] = []
    invoices: list[OrderInvoiceResponse] = []
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
