from uuid import UUID

from pydantic import BaseModel, Field


class CartItemAdd(BaseModel):
    product_id: UUID
    quantity: int = Field(default=1, ge=1, le=100)
    variant_asin: str | None = Field(default=None, max_length=20, pattern=r"^[A-Z0-9]{10,20}$")


class CartItemUpdate(BaseModel):
    quantity: int = Field(ge=1, le=100)


class CartItemResponse(BaseModel):
    id: UUID
    product_id: UUID
    product_name: str
    quantity: int
    price_at_add_cents: int
    current_price_cents: int
    price_changed: bool
    price_diff_cents: int
    product_active: bool
    image_url: str | None = None
    external_url: str = ""
    max_quantity_per_user: int = 1
    variant_asin: str | None = None
    variant_value: str | None = None


class CartResponse(BaseModel):
    items: list[CartItemResponse]
    total_at_add_cents: int
    total_current_cents: int
    has_price_changes: bool
    has_unavailable_items: bool
    available_budget_cents: int
    budget_exceeded: bool
