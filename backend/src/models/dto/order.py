from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from src.core.validators import validate_http_url
from src.models.dto.common import PaginatedResponse


class OrderCreate(BaseModel):
    delivery_note: str | None = Field(default=None, max_length=2000)
    confirm_price_changes: bool = False


class OrderStatusUpdate(BaseModel):
    status: Literal["ordered", "delivered", "rejected", "cancelled", "return_requested", "returned"]
    admin_note: str | None = Field(default=None, max_length=2000)
    expected_delivery: str | None = Field(default=None, max_length=255)
    purchase_url: str | None = Field(default=None, max_length=2048)
    tracking_number: str | None = Field(default=None, max_length=255)
    tracking_url: str | None = Field(default=None, max_length=2048)

    @field_validator("purchase_url", "tracking_url")
    @classmethod
    def validate_purchase_url_scheme(cls, v):
        return validate_http_url(v)


class OrderCancelRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=1000)


class OrderPurchaseUrlUpdate(BaseModel):
    purchase_url: str | None = Field(default=None, max_length=2048)

    @field_validator("purchase_url")
    @classmethod
    def validate_purchase_url_scheme(cls, v):
        return validate_http_url(v)


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


class OrderTrackingUpdateResponse(BaseModel):
    id: UUID
    comment: str
    created_by: UUID
    created_by_name: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class OrderTrackingInfoUpdate(BaseModel):
    tracking_number: str | None = Field(default=None, max_length=255)
    tracking_url: str | None = Field(default=None, max_length=2048)
    comment: str | None = Field(default=None, max_length=2000)

    @field_validator("tracking_url")
    @classmethod
    def validate_tracking_url_scheme(cls, v):
        return validate_http_url(v)


class OrderResponse(BaseModel):
    id: UUID
    user_id: UUID
    user_email: str | None = None
    user_display_name: str | None = None
    status: Literal["pending", "ordered", "delivered", "rejected", "cancelled", "return_requested", "returned"]
    total_cents: int
    delivery_note: str | None = None
    admin_note: str | None = None
    expected_delivery: str | None = None
    purchase_url: str | None = None
    tracking_number: str | None = None
    tracking_url: str | None = None
    aftership_tracking_id: str | None = None
    aftership_slug: str | None = None
    tracking_updates: list[OrderTrackingUpdateResponse] = []
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


OrderListResponse = PaginatedResponse[OrderResponse]


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
