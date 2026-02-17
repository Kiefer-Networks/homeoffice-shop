from uuid import UUID

from pydantic import BaseModel


class CartItemAdd(BaseModel):
    product_id: UUID
    quantity: int = 1


class CartItemUpdate(BaseModel):
    quantity: int


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


class CartResponse(BaseModel):
    items: list[CartItemResponse]
    total_at_add_cents: int
    total_current_cents: int
    has_price_changes: bool
    has_unavailable_items: bool
    available_budget_cents: int
    budget_exceeded: bool
