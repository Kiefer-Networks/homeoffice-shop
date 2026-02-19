from datetime import datetime
from typing import Literal
from urllib.parse import urlparse
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class OrderCreate(BaseModel):
    delivery_note: str | None = Field(default=None, max_length=2000)
    confirm_price_changes: bool = False


class OrderStatusUpdate(BaseModel):
    status: Literal["ordered", "delivered", "rejected", "cancelled"]
    admin_note: str | None = Field(default=None, max_length=2000)
    expected_delivery: str | None = Field(default=None, max_length=255)
    purchase_url: str | None = Field(default=None, max_length=2048)

    @field_validator("purchase_url")
    @classmethod
    def validate_purchase_url_scheme(cls, v: str | None) -> str | None:
        if v is not None:
            parsed = urlparse(v)
            if parsed.scheme not in ("http", "https") or not parsed.netloc:
                raise ValueError("purchase_url must be a valid http:// or https:// URL")
        return v


class OrderCancelRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=1000)


class OrderPurchaseUrlUpdate(BaseModel):
    purchase_url: str | None = Field(default=None, max_length=2048)

    @field_validator("purchase_url")
    @classmethod
    def validate_purchase_url_scheme(cls, v: str | None) -> str | None:
        if v is not None:
            parsed = urlparse(v)
            if parsed.scheme not in ("http", "https") or not parsed.netloc:
                raise ValueError("purchase_url must be a valid http:// or https:// URL")
        return v


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
    status: Literal["pending", "ordered", "delivered", "rejected", "cancelled"]
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
    hibob_synced_at: datetime | None = None

    model_config = {"from_attributes": True}


class OrderListResponse(BaseModel):
    items: list[OrderResponse]
    total: int
    page: int
    per_page: int


class OrderItemCheckUpdate(BaseModel):
    vendor_ordered: bool


class OrderItemCheckResponse(BaseModel):
    detail: str
    vendor_ordered: bool


class OrderHiBobSyncResponse(BaseModel):
    detail: str
    synced_at: datetime | None = None
    order: OrderResponse | None = None


class OrderHiBobUnsyncResponse(BaseModel):
    detail: str
    order: OrderResponse | None = None
