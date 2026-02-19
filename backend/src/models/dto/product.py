from datetime import datetime
from typing import Any
from urllib.parse import urlparse
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class ProductCreate(BaseModel):
    category_id: UUID
    name: str = Field(min_length=1, max_length=500)
    description: str | None = None
    brand: str | None = None
    brand_id: UUID
    model: str | None = None
    price_cents: int = Field(ge=0)
    amazon_asin: str | None = None
    external_url: str
    is_active: bool = True
    max_quantity_per_user: int = Field(default=1, ge=1, le=100)

    @field_validator("external_url")
    @classmethod
    def validate_url_scheme(cls, v: str) -> str:
        parsed = urlparse(v)
        if parsed.scheme not in ("https", "http") or not parsed.netloc:
            raise ValueError("URL must be a valid http:// or https:// URL")
        return v


class ProductUpdate(BaseModel):
    category_id: UUID | None = None
    name: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = None
    brand: str | None = None
    brand_id: UUID | None = None
    model: str | None = None
    price_cents: int | None = Field(default=None, ge=0)
    amazon_asin: str | None = None
    external_url: str | None = None
    is_active: bool | None = None
    max_quantity_per_user: int | None = Field(default=None, ge=1, le=100)

    @field_validator("external_url")
    @classmethod
    def validate_url_scheme(cls, v: str | None) -> str | None:
        if v is not None:
            parsed = urlparse(v)
            if parsed.scheme not in ("https", "http") or not parsed.netloc:
                raise ValueError("URL must be a valid http:// or https:// URL")
        return v


class ProductResponse(BaseModel):
    id: UUID
    category_id: UUID
    name: str
    description: str | None = None
    brand: str | None = None
    model: str | None = None
    image_url: str | None = None
    image_gallery: list[str] | None = None
    specifications: dict[str, Any] | None = None
    price_cents: int
    price_min_cents: int | None = None
    price_max_cents: int | None = None
    color: str | None = None
    material: str | None = None
    product_dimensions: str | None = None
    item_weight: str | None = None
    item_model_number: str | None = None
    product_information: dict[str, Any] | None = None
    variants: list[dict[str, Any]] | None = None
    amazon_asin: str | None = None
    external_url: str
    brand_id: UUID | None = None
    is_active: bool
    archived_at: datetime | None = None
    max_quantity_per_user: int = 1
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProductListResponse(BaseModel):
    items: list[ProductResponse]
    total: int
    page: int
    per_page: int
    facets: dict[str, Any] | None = None


class AmazonSearchResponse(BaseModel):
    name: str
    asin: str
    price_cents: int = 0
    image_url: str | None = None
    url: str | None = None
    rating: float | None = None
    reviews: int | None = None


class AmazonProductResponse(BaseModel):
    name: str
    description: str | None = None
    brand: str | None = None
    images: list[str] = []
    price_cents: int = 0
    specifications: dict[str, Any] | None = None
    feature_bullets: list[str] = []
    url: str | None = None
    color: str | None = None
    material: str | None = None
    product_dimensions: str | None = None
    item_weight: str | None = None
    item_model_number: str | None = None
    product_information: dict[str, Any] | None = None
    variants: list[dict[str, Any]] = []


class ProductFieldDiff(BaseModel):
    field: str
    label: str
    old_value: str | int | float | bool | dict[str, Any] | list | None
    new_value: str | int | float | bool | dict[str, Any] | list | None


class RefreshPreviewResponse(BaseModel):
    product_id: UUID
    images_updated: bool
    image_url: str | None = None
    image_gallery: list[str] | None = None
    diffs: list[ProductFieldDiff]


class RefreshApplyRequest(BaseModel):
    fields: list[str]
    values: dict[str, str | int | float | bool | list | dict | None]
