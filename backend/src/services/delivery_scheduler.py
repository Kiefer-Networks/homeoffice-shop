import asyncio
import logging
from datetime import datetime, timezone

from src.core.database import async_session_factory
from src.services.settings_service import load_settings

logger = logging.getLogger(__name__)

_scheduler_task: asyncio.Task | None = None

REMINDER_HOUR = 8  # UTC


async def _scheduler_loop() -> None:
    """Check once per minute whether delivery reminders should be sent."""
    last_run_date: str | None = None

    while True:
        await asyncio.sleep(60)
        try:
            now = datetime.now(timezone.utc)

            # Run once daily during REMINDER_HOUR (any minute, deduped by last_run_date)
            if now.hour != REMINDER_HOUR:
                continue

            run_key = now.strftime("%Y-%m-%d")
            if last_run_date == run_key:
                continue

            last_run_date = run_key
            logger.info("Delivery reminder check triggered at %s", now.isoformat())

            async with async_session_factory() as db:
                await load_settings(db)
                from src.services.delivery_reminder import send_delivery_reminders
                sent = await send_delivery_reminders(db)
                await db.commit()

            if sent:
                logger.info("Sent %d delivery reminder(s)", sent)
            else:
                logger.debug("No delivery reminders to send")
        except Exception:
            logger.exception("Delivery reminder check failed")


def start_delivery_scheduler() -> None:
    global _scheduler_task
    if _scheduler_task is None or _scheduler_task.done():
        _scheduler_task = asyncio.create_task(_scheduler_loop())
        logger.info("Delivery reminder scheduler started")


def stop_delivery_scheduler() -> None:
    global _scheduler_task
    if _scheduler_task and not _scheduler_task.done():
        _scheduler_task.cancel()
        _scheduler_task = None
        logger.info("Delivery reminder scheduler stopped")
