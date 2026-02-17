import logging
import re
import time
from typing import Protocol, runtime_checkable

import httpx

from src.core.config import settings
from src.integrations.amazon.models import AmazonProduct, AmazonSearchResult

logger = logging.getLogger(__name__)

SCRAPER_BASE = "https://api.scraperapi.com/structured/amazon"
_CACHE_TTL = 300  # 5 minutes
_product_cache: dict[str, tuple[float, AmazonProduct]] = {}


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
            "language": "en",
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(f"{SCRAPER_BASE}/search", params=params)
            resp.raise_for_status()
            data = resp.json()

        logger.info("ScraperAPI search returned %d results for query=%r", len(data.get("results", [])), query)

        results = []
        for item in data.get("results", []):
            url = item.get("url", "")
            asin = _extract_asin(url) or item.get("asin", "")
            if not asin:
                continue
            price_str = item.get("price_string") or item.get("price") or item.get("pricing") or ""
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
        # Check cache first
        cached = _product_cache.get(asin)
        if cached:
            ts, product = cached
            if time.monotonic() - ts < _CACHE_TTL:
                logger.info("Cache hit for ASIN %s", asin)
                return product
            del _product_cache[asin]

        params = {
            "api_key": settings.scraperapi_api_key,
            "asin": asin,
            "tld": settings.amazon_tld,
            "country_code": settings.amazon_country_code,
            "language": "en",
        }
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(f"{SCRAPER_BASE}/product", params=params)
            resp.raise_for_status()
            data = resp.json()

        if not data:
            logger.warning("ScraperAPI returned empty data for ASIN %s", asin)
            return None

        logger.info(
            "ScraperAPI raw data for ASIN %s: price=%r, price_string=%r, "
            "pricing=%r, price_upper=%r, name=%r, brand=%r, "
            "images_count=%d, specs_count=%d, bullets_count=%d",
            asin,
            data.get("price"),
            data.get("price_string"),
            data.get("pricing"),
            data.get("price_upper"),
            data.get("name"),
            data.get("brand"),
            len(data.get("images", [])),
            len(data.get("specifications", [])),
            len(data.get("feature_bullets", [])),
        )

        price_str = (
            data.get("price_string")
            or data.get("price")
            or (data.get("pricing") or "")
            or ""
        )
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

        parsed_price = _parse_price_cents(str(price_str)) if price_str else 0
        logger.info(
            "ScraperAPI ASIN %s: price_str=%r -> parsed_price_cents=%d",
            asin, price_str, parsed_price,
        )

        # Extract product_information dict (flat key-value pairs from Amazon)
        product_info = data.get("product_information", {})
        if isinstance(product_info, list):
            # Sometimes returned as list of {name, value} dicts
            pi = {}
            for item in product_info:
                if isinstance(item, dict):
                    k = item.get("name") or item.get("key", "")
                    v = item.get("value", "")
                    if k:
                        pi[k] = v
            product_info = pi
        elif not isinstance(product_info, dict):
            product_info = {}

        # Prefer clean brand from product_information over polluted top-level brand
        brand = product_info.get("brand") or product_info.get("Brand") or data.get("brand")

        result = AmazonProduct(
            name=data.get("name", ""),
            description=data.get("description"),
            brand=brand,
            images=images,
            price_cents=parsed_price,
            specifications=specs or None,
            feature_bullets=data.get("feature_bullets", []),
            url=f"https://www.amazon.{settings.amazon_tld}/dp/{asin}",
            color=product_info.get("colour") or product_info.get("color") or product_info.get("Colour") or product_info.get("Color"),
            material=product_info.get("material") or product_info.get("Material"),
            product_dimensions=product_info.get("product_dimensions") or product_info.get("Product Dimensions") or product_info.get("Product dimensions"),
            item_weight=product_info.get("item_weight") or product_info.get("Item Weight") or product_info.get("Item weight"),
            item_model_number=product_info.get("item_model_number") or product_info.get("Item model number") or product_info.get("model_number"),
            product_information=product_info or None,
        )

        # Cache the result
        _product_cache[asin] = (time.monotonic(), result)
        # Evict old entries if cache grows too large
        if len(_product_cache) > 100:
            now = time.monotonic()
            expired = [k for k, (ts, _) in _product_cache.items() if now - ts >= _CACHE_TTL]
            for k in expired:
                del _product_cache[k]

        return result

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
