from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class BrandCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class BrandUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    logo_url: str | None = None


class BrandResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    logo_url: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
