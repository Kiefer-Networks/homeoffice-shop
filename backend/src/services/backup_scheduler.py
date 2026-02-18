import asyncio
import logging
from datetime import datetime, timezone

from src.services.settings_service import get_setting

logger = logging.getLogger(__name__)

_scheduler_task: asyncio.Task | None = None


async def _scheduler_loop() -> None:
    """Check once per minute whether a scheduled backup should run."""
    last_run_date: str | None = None

    while True:
        await asyncio.sleep(60)
        try:
            enabled = get_setting("backup_schedule_enabled") == "true"
            if not enabled:
                continue

            hour = int(get_setting("backup_schedule_hour") or "2")
            minute = int(get_setting("backup_schedule_minute") or "0")

            now = datetime.now(timezone.utc)
            today = now.strftime("%Y-%m-%d")

            if now.hour == hour and now.minute == minute and last_run_date != today:
                last_run_date = today
                logger.info("Scheduled backup triggered at %s", now.isoformat())
                from src.api.routes.admin.backup import run_backup
                await run_backup(triggered_by="scheduler")
                logger.info("Scheduled backup completed")
        except Exception:
            logger.exception("Scheduled backup failed")


def start_backup_scheduler() -> None:
    global _scheduler_task
    if _scheduler_task is None or _scheduler_task.done():
        _scheduler_task = asyncio.create_task(_scheduler_loop())
        logger.info("Backup scheduler started")


def stop_backup_scheduler() -> None:
    global _scheduler_task
    if _scheduler_task and not _scheduler_task.done():
        _scheduler_task.cancel()
        _scheduler_task = None
        logger.info("Backup scheduler stopped")
