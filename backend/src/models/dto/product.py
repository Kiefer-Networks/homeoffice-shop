from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ProductCreate(BaseModel):
    category_id: UUID
    name: str = Field(min_length=1, max_length=500)
    description: str | None = None
    brand: str | None = None
    model: str | None = None
    price_cents: int = Field(ge=0)
    amazon_asin: str | None = None
    external_url: str
    is_active: bool = True
    max_quantity_per_user: int = Field(default=1, ge=1, le=100)


class ProductUpdate(BaseModel):
    category_id: UUID | None = None
    name: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = None
    brand: str | None = None
    model: str | None = None
    price_cents: int | None = Field(default=None, ge=0)
    amazon_asin: str | None = None
    external_url: str | None = None
    is_active: bool | None = None
    max_quantity_per_user: int | None = Field(default=None, ge=1, le=100)


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
    color: str | None = None
    material: str | None = None
    product_dimensions: str | None = None
    item_weight: str | None = None
    item_model_number: str | None = None
    product_information: dict | None = None
    amazon_asin: str | None = None
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


class AmazonSearchRequest(BaseModel):
    query: str


class AmazonSearchResponse(BaseModel):
    name: str
    asin: str
    price_cents: int = 0
    image_url: str | None = None
    url: str | None = None
    rating: float | None = None
    reviews: int | None = None


class AmazonProductRequest(BaseModel):
    asin: str


class AmazonProductResponse(BaseModel):
    name: str
    description: str | None = None
    brand: str | None = None
    images: list[str] = []
    price_cents: int = 0
    specifications: dict | None = None
    feature_bullets: list[str] = []
    url: str | None = None
    color: str | None = None
    material: str | None = None
    product_dimensions: str | None = None
    item_weight: str | None = None
    item_model_number: str | None = None
    product_information: dict | None = None
