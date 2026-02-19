from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=1, max_length=255, pattern=r"^[a-z0-9-]+$")
    description: str | None = Field(default=None, max_length=2000)
    icon: str | None = None
    sort_order: int = 0


class CategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    slug: str | None = Field(default=None, min_length=1, max_length=255, pattern=r"^[a-z0-9-]+$")
    description: str | None = Field(default=None, max_length=2000)
    icon: str | None = None
    sort_order: int | None = None


class CategoryReorderItem(BaseModel):
    id: UUID
    sort_order: int


class CategoryResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    description: str | None = None
    icon: str | None = None
    sort_order: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}
