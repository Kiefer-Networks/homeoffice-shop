from pydantic import BaseModel


class AmazonSearchResult(BaseModel):
    name: str
    asin: str
    price_cents: int = 0
    image_url: str | None = None
    url: str | None = None
    rating: float | None = None
    reviews: int | None = None


class AmazonVariant(BaseModel):
    group: str
    value: str
    asin: str
    is_selected: bool = False
    image_url: str | None = None
    price_cents: int = 0


class AmazonProduct(BaseModel):
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
    variants: list[AmazonVariant] = []
