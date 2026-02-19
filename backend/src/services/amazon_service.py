import logging

from src.integrations.amazon.client import AmazonClient
from src.integrations.amazon.models import AmazonProduct, AmazonSearchResult

logger = logging.getLogger(__name__)


async def search_products(keywords: str) -> list[AmazonSearchResult]:
    """Search Amazon products by keywords."""
    client = AmazonClient()
    results = await client.search(keywords)
    return results


async def get_product(asin: str) -> AmazonProduct | None:
    """Fetch a single Amazon product by ASIN."""
    client = AmazonClient()
    return await client.get_product(asin)
