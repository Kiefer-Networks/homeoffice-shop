from pydantic import BaseModel


class AmazonSearchResult(BaseModel):
    name: str
    asin: str
    price_cents: int = 0
    image_url: str | None = None
    url: str | None = None
    rating: float | None = None
    reviews: int | None = None


class AmazonProduct(BaseModel):
    name: str
    description: str | None = None
    brand: str | None = None
    images: list[str] = []
    price_cents: int = 0
    specifications: dict | None = None
    feature_bullets: list[str] = []
    url: str | None = None
