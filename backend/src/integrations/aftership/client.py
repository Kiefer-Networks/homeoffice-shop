import asyncio
import logging
from dataclasses import dataclass

import httpx

from src.core.config import settings

logger = logging.getLogger(__name__)

AFTERSHIP_API_BASE = "https://api.aftership.com/tracking/2024-10"

# Map AfterShip status tags to our internal order statuses
AFTERSHIP_TAG_TO_STATUS: dict[str, str | None] = {
    "Pending": None,          # not actionable yet
    "InfoReceived": None,
    "InTransit": None,
    "OutForDelivery": None,
    "AttemptFail": None,
    "AvailableForPickup": None,
    "Delivered": "delivered",  # auto-transition trigger
    "Exception": None,        # carrier exception, don't auto-change
    "Expired": None,
}

# Mapping from our detectCarrier names to AfterShip slugs
CARRIER_SLUG_MAP: dict[str, str] = {
    "Amazon (Swiship)": "swiship",
    "Amazon Logistics": "amazon",
    "UPS": "ups",
    "DHL Express": "dhl",
    "DHL Paket": "dhl-germany",
    "DPD": "dpd-de",
    "Hermes": "hermes-de",
    "GLS": "gls",
}


@dataclass
class AfterShipTracking:
    id: str
    tracking_number: str
    slug: str
    tag: str
    subtag: str
    subtag_message: str
    checkpoints: list[dict]
    tracking_url: str | None = None


class AfterShipClient:
    def __init__(self) -> None:
        self._api_key = settings.aftership_api_key

    @property
    def is_configured(self) -> bool:
        return bool(self._api_key)

    def _headers(self) -> dict[str, str]:
        return {
            "as-api-key": self._api_key,
            "Content-Type": "application/json",
        }

    async def create_tracking(
        self,
        tracking_number: str,
        slug: str | None = None,
        order_id: str | None = None,
    ) -> AfterShipTracking | None:
        """Register a tracking number with AfterShip. Returns tracking info or None on failure."""
        payload: dict = {"tracking_number": tracking_number}
        if slug:
            payload["slug"] = slug
        if order_id:
            payload["order_id"] = order_id

        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.post(
                        f"{AFTERSHIP_API_BASE}/trackings",
                        headers=self._headers(),
                        json=payload,
                    )

                    body = resp.json()
                    meta_code = body.get("meta", {}).get("code", resp.status_code)

                    if meta_code == 4003:
                        # Already exists — return existing tracking info
                        existing_data = body.get("data", {})
                        existing_id = existing_data.get("id")
                        logger.info("Tracking %s already exists in AfterShip (id=%s)", tracking_number, existing_id)
                        if existing_id:
                            return await self.get_tracking_by_id(existing_id)
                        return await self.get_tracking(tracking_number, slug)

                    if resp.status_code == 429 and attempt < 2:
                        wait = 2 ** attempt
                        logger.warning("AfterShip rate limit, retrying in %ds", wait)
                        await asyncio.sleep(wait)
                        continue

                    if resp.status_code >= 400:
                        logger.error(
                            "AfterShip create_tracking failed (%d): %s",
                            resp.status_code, resp.text,
                        )
                        return None

                    data = body.get("data", {})
                    return self._parse_tracking(data)

            except httpx.TimeoutException:
                logger.warning("AfterShip create_tracking timeout (attempt %d)", attempt + 1)
                if attempt < 2:
                    await asyncio.sleep(2 ** attempt)
            except Exception:
                logger.exception("AfterShip create_tracking error")
                return None

        return None

    async def get_tracking_by_id(
        self,
        aftership_id: str,
    ) -> AfterShipTracking | None:
        """Get tracking by AfterShip ID (most reliable lookup method)."""
        return await self._get(f"{AFTERSHIP_API_BASE}/trackings/{aftership_id}")

    async def get_tracking(
        self,
        tracking_number: str,
        slug: str | None = None,
    ) -> AfterShipTracking | None:
        """Get current tracking status from AfterShip by tracking number."""
        if slug:
            path = f"{AFTERSHIP_API_BASE}/trackings/{slug}/{tracking_number}"
        else:
            path = f"{AFTERSHIP_API_BASE}/trackings?tracking_numbers={tracking_number}"

        return await self._get(path)

    async def _get(self, path: str) -> AfterShipTracking | None:
        """Internal GET helper with retries and parsing."""
        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.get(path, headers=self._headers())

                    if resp.status_code == 404:
                        return None

                    if resp.status_code == 429 and attempt < 2:
                        wait = 2 ** attempt
                        logger.warning("AfterShip rate limit, retrying in %ds", wait)
                        await asyncio.sleep(wait)
                        continue

                    if resp.status_code >= 400:
                        logger.error(
                            "AfterShip GET %s failed (%d): %s",
                            path, resp.status_code, resp.text,
                        )
                        return None

                    body = resp.json().get("data", {})
                    # Direct ID or slug+number lookup
                    if isinstance(body, dict) and "tracking_number" in body:
                        return self._parse_tracking(body)
                    # Nested tracking key
                    if "tracking" in body:
                        return self._parse_tracking(body["tracking"])
                    # Search returns list
                    trackings = body.get("trackings", [])
                    if trackings:
                        return self._parse_tracking(trackings[0])
                    return None

            except httpx.TimeoutException:
                logger.warning("AfterShip GET timeout (attempt %d)", attempt + 1)
                if attempt < 2:
                    await asyncio.sleep(2 ** attempt)
            except Exception:
                logger.exception("AfterShip GET error")
                return None

        return None

    async def get_all_trackings(self) -> list[AfterShipTracking]:
        """Fetch ALL trackings in a single paginated call (up to 200 per page).

        Used for scheduled batch sync — 1 API call instead of N.
        """
        results: list[AfterShipTracking] = []
        cursor: str | None = None

        while True:
            params = "limit=200"
            if cursor:
                params += f"&cursor={cursor}"

            path = f"{AFTERSHIP_API_BASE}/trackings?{params}"

            for attempt in range(3):
                try:
                    async with httpx.AsyncClient(timeout=30.0) as client:
                        resp = await client.get(path, headers=self._headers())

                        if resp.status_code == 429 and attempt < 2:
                            wait = 2 ** attempt
                            logger.warning("AfterShip rate limit on list, retrying in %ds", wait)
                            await asyncio.sleep(wait)
                            continue

                        if resp.status_code >= 400:
                            logger.error("AfterShip list failed (%d): %s", resp.status_code, resp.text)
                            return results

                        body = resp.json().get("data", {})
                        for t in body.get("trackings", []):
                            results.append(self._parse_tracking(t))

                        pagination = body.get("pagination", {})
                        if pagination.get("has_next_page") and pagination.get("next_cursor"):
                            cursor = pagination["next_cursor"]
                        else:
                            return results

                        break  # success, move to next page

                except httpx.TimeoutException:
                    logger.warning("AfterShip list timeout (attempt %d)", attempt + 1)
                    if attempt < 2:
                        await asyncio.sleep(2 ** attempt)
                    else:
                        return results
                except Exception:
                    logger.exception("AfterShip list error")
                    return results

        return results

    def _parse_tracking(self, data: dict) -> AfterShipTracking:
        return AfterShipTracking(
            id=data.get("id", ""),
            tracking_number=data.get("tracking_number", ""),
            slug=data.get("slug", ""),
            tag=data.get("tag", ""),
            subtag=data.get("subtag", ""),
            subtag_message=data.get("subtag_message", ""),
            checkpoints=data.get("checkpoints", []),
            tracking_url=data.get("courier_tracking_link"),
        )


aftership_client = AfterShipClient()
