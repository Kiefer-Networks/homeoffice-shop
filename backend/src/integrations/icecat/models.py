from pydantic import BaseModel


class IcecatProduct(BaseModel):
    title: str | None = None
    description: str | None = None
    brand: str | None = None
    model: str | None = None
    main_image_url: str | None = None
    gallery_urls: list[str] = []
    specifications: dict | None = None
    price_cents: int = 0
