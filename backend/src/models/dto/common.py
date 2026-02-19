from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    per_page: int


class CountResponse(BaseModel):
    count: int


class BrandingResponse(BaseModel):
    company_name: str
