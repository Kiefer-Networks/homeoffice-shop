import logging

import httpx

from src.core.config import settings

logger = logging.getLogger(__name__)


async def send_slack_message(text: str, blocks: list[dict] | None = None) -> bool:
    if not settings.slack_webhook_url:
        logger.debug("Slack not configured, skipping message")
        return False

    try:
        payload: dict = {"text": text}
        if blocks:
            payload["blocks"] = blocks

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(settings.slack_webhook_url, json=payload)
            resp.raise_for_status()

        logger.info("Slack message sent successfully")
        return True
    except Exception:
        logger.exception("Failed to send Slack message")
        return False
