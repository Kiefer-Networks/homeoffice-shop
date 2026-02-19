from datetime import datetime
from urllib.parse import urlparse
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class BrandCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class BrandUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    logo_url: str | None = None

    @field_validator("logo_url")
    @classmethod
    def validate_logo_url(cls, v: str | None) -> str | None:
        if v is None:
            return v
        parsed = urlparse(v)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError("logo_url must be a valid https:// URL")
        return v


class BrandResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    logo_url: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
