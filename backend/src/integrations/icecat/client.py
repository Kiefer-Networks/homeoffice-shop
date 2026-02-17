import logging
from typing import Protocol, runtime_checkable

import httpx

from src.core.config import settings
from src.integrations.icecat.models import IcecatProduct

logger = logging.getLogger(__name__)

ICECAT_API_BASE = "https://live.icecat.biz/api/"


@runtime_checkable
class IcecatClientProtocol(Protocol):
    async def lookup_by_gtin(self, gtin: str) -> IcecatProduct | None: ...
    async def get_current_price(self, gtin: str) -> int | None: ...


class IcecatClient:
    async def lookup_by_gtin(self, gtin: str) -> IcecatProduct | None:
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    ICECAT_API_BASE,
                    params={
                        "Language": settings.icecat_language,
                        "GTIN": gtin,
                    },
                    headers={"api-token": settings.icecat_api_token},
                )
                resp.raise_for_status()
                data = resp.json()

            product_data = data.get("data", {})
            general = product_data.get("GeneralInfo", {})
            gallery = product_data.get("Gallery", [])
            image = product_data.get("Image", {})

            gallery_urls = []
            for img in gallery:
                url = img.get("Pic", "") or img.get("Pic500x500", "")
                if url:
                    gallery_urls.append(url)

            specs = {}
            for group in product_data.get("FeaturesGroups", []):
                group_name = group.get("FeatureGroup", {}).get("Name", {}).get("Value", "")
                features = []
                for feat in group.get("Features", []):
                    feat_name = feat.get("Feature", {}).get("Name", {}).get("Value", "")
                    feat_value = feat.get("PresentationValue", "")
                    if feat_name and feat_value:
                        features.append({"name": feat_name, "value": feat_value})
                if group_name and features:
                    specs[group_name] = features

            price_cents = 0
            offers = product_data.get("Offers", [])
            if offers:
                try:
                    price = float(offers[0].get("Price", 0))
                    price_cents = int(price * 100)
                except (ValueError, TypeError, IndexError):
                    pass

            return IcecatProduct(
                title=general.get("Title") or general.get("ProductName"),
                description=general.get("Description", {}).get("LongDesc", "")
                or general.get("SummaryDescription", {}).get("LongSummaryDescription", ""),
                brand=general.get("BrandInfo", {}).get("BrandName"),
                model=general.get("ProductName"),
                main_image_url=image.get("HighPic") or image.get("MediumPic"),
                gallery_urls=gallery_urls[:10],
                specifications=specs if specs else None,
                price_cents=price_cents,
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            logger.exception("Icecat lookup failed for GTIN %s", gtin)
            return None
        except Exception:
            logger.exception("Icecat lookup failed for GTIN %s", gtin)
            return None

    async def get_current_price(self, gtin: str) -> int | None:
        product = await self.lookup_by_gtin(gtin)
        if product and product.price_cents > 0:
            return product.price_cents
        return None


class FakeIcecatClient:
    """Test fake returning predefined data."""

    def __init__(self, products: dict[str, IcecatProduct] | None = None):
        self.products = products or {}

    async def lookup_by_gtin(self, gtin: str) -> IcecatProduct | None:
        return self.products.get(gtin)

    async def get_current_price(self, gtin: str) -> int | None:
        product = self.products.get(gtin)
        if product and product.price_cents > 0:
            return product.price_cents
        return None
