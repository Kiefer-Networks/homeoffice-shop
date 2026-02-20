import logging
import re

import httpx

from src.core.config import settings

logger = logging.getLogger(__name__)

_SLACK_MENTION_RE = re.compile(r"@(channel|here|everyone)")


def sanitize_slack_text(text: str) -> str:
    """Escape Slack special characters and @-mentions in user-provided text."""
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = _SLACK_MENTION_RE.sub(r"@\u200B\1", text)
    return text


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
