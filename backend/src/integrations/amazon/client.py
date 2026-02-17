import logging
import re
from typing import Protocol, runtime_checkable

import httpx

from src.core.config import settings
from src.integrations.amazon.models import AmazonProduct, AmazonSearchResult

logger = logging.getLogger(__name__)

SCRAPER_BASE = "https://api.scraperapi.com/structured/amazon"


def _extract_asin(url: str) -> str | None:
    """Extract ASIN from an Amazon product URL."""
    match = re.search(r"/dp/([A-Z0-9]{10})", url)
    if match:
        return match.group(1)
    match = re.search(r"/gp/product/([A-Z0-9]{10})", url)
    if match:
        return match.group(1)
    return None


def _parse_price_cents(price_str: str | None) -> int:
    """Parse a price string like '$29.99' or '29,99' into cents."""
    if not price_str:
        return 0
    cleaned = re.sub(r"[^\d.,]", "", price_str)
    if not cleaned:
        return 0
    # Handle European format (29,99) vs US format (29.99)
    if "," in cleaned and "." in cleaned:
        # e.g. "1.234,56" -> European
        cleaned = cleaned.replace(".", "").replace(",", ".")
    elif "," in cleaned:
        cleaned = cleaned.replace(",", ".")
    try:
        return int(round(float(cleaned) * 100))
    except ValueError:
        return 0


@runtime_checkable
class AmazonClientProtocol(Protocol):
    async def search(self, query: str) -> list[AmazonSearchResult]: ...
    async def get_product(self, asin: str) -> AmazonProduct | None: ...
    async def get_current_price(self, asin: str) -> int | None: ...


class AmazonClient:
    """Real ScraperAPI-backed Amazon client."""

    async def search(self, query: str) -> list[AmazonSearchResult]:
        params = {
            "api_key": settings.scraperapi_api_key,
            "query": query,
            "tld": settings.amazon_tld,
            "country_code": settings.amazon_country_code,
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(f"{SCRAPER_BASE}/search", params=params)
            resp.raise_for_status()
            data = resp.json()

        results = []
        for item in data.get("results", []):
            url = item.get("url", "")
            asin = _extract_asin(url) or item.get("asin", "")
            if not asin:
                continue
            price_str = item.get("price_string") or item.get("price") or ""
            results.append(AmazonSearchResult(
                name=item.get("name", ""),
                asin=asin,
                price_cents=_parse_price_cents(str(price_str)) if price_str else 0,
                image_url=item.get("image"),
                url=url,
                rating=item.get("rating"),
                reviews=item.get("total_reviews"),
            ))
        return results

    async def get_product(self, asin: str) -> AmazonProduct | None:
        params = {
            "api_key": settings.scraperapi_api_key,
            "asin": asin,
            "tld": settings.amazon_tld,
            "country_code": settings.amazon_country_code,
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(f"{SCRAPER_BASE}/product", params=params)
            resp.raise_for_status()
            data = resp.json()

        if not data:
            return None

        price_str = data.get("price_string") or data.get("price") or ""
        images = data.get("images", [])
        if isinstance(images, list):
            images = [img for img in images if isinstance(img, str)]
        else:
            images = []

        specs = {}
        for spec in data.get("specifications", []):
            if isinstance(spec, dict):
                key = spec.get("name") or spec.get("key", "")
                val = spec.get("value", "")
                if key:
                    specs[key] = val

        return AmazonProduct(
            name=data.get("name", ""),
            description=data.get("description"),
            brand=data.get("brand"),
            images=images,
            price_cents=_parse_price_cents(str(price_str)) if price_str else 0,
            specifications=specs or None,
            feature_bullets=data.get("feature_bullets", []),
            url=f"https://www.amazon.{settings.amazon_tld}/dp/{asin}",
        )

    async def get_current_price(self, asin: str) -> int | None:
        product = await self.get_product(asin)
        if product and product.price_cents > 0:
            return product.price_cents
        return None


class FakeAmazonClient:
    """Test double for AmazonClient."""

    def __init__(self, products: dict[str, AmazonProduct] | None = None):
        self._products = products or {}

    async def search(self, query: str) -> list[AmazonSearchResult]:
        results = []
        for asin, product in self._products.items():
            if query.lower() in product.name.lower() or query == asin:
                results.append(AmazonSearchResult(
                    name=product.name,
                    asin=asin,
                    price_cents=product.price_cents,
                    image_url=product.images[0] if product.images else None,
                    url=product.url,
                ))
        return results

    async def get_product(self, asin: str) -> AmazonProduct | None:
        return self._products.get(asin)

    async def get_current_price(self, asin: str) -> int | None:
        product = self._products.get(asin)
        if product and product.price_cents > 0:
            return product.price_cents
        return None
