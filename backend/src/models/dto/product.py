from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ProductCreate(BaseModel):
    category_id: UUID
    name: str
    description: str | None = None
    brand: str | None = None
    model: str | None = None
    price_cents: int
    icecat_gtin: str | None = None
    external_url: str
    is_active: bool = True
    max_quantity_per_user: int = 1


class ProductUpdate(BaseModel):
    category_id: UUID | None = None
    name: str | None = None
    description: str | None = None
    brand: str | None = None
    model: str | None = None
    price_cents: int | None = None
    icecat_gtin: str | None = None
    external_url: str | None = None
    is_active: bool | None = None
    max_quantity_per_user: int | None = None


class ProductResponse(BaseModel):
    id: UUID
    category_id: UUID
    name: str
    description: str | None = None
    brand: str | None = None
    model: str | None = None
    image_url: str | None = None
    image_gallery: list[str] | None = None
    specifications: dict | None = None
    price_cents: int
    price_min_cents: int | None = None
    price_max_cents: int | None = None
    icecat_gtin: str | None = None
    external_url: str
    is_active: bool
    max_quantity_per_user: int = 1
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProductListResponse(BaseModel):
    items: list[ProductResponse]
    total: int
    page: int
    per_page: int
    facets: dict | None = None


class IcecatLookupRequest(BaseModel):
    gtin: str


class IcecatLookupResponse(BaseModel):
    name: str | None = None
    description: str | None = None
    brand: str | None = None
    model: str | None = None
    main_image_url: str | None = None
    gallery_urls: list[str] = []
    specifications: dict | None = None
    price_cents: int = 0
