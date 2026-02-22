import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path

from src.services.settings_service import get_setting

logger = logging.getLogger(__name__)


async def _audit_scheduled_backup(filename: str, triggered_by: str) -> None:
    """Write audit log entry for a scheduled backup (no HTTP request context)."""
    try:
        from src.audit.service import write_audit_log
        from src.core.database import async_session_factory
        from src.core.config import settings
        from src.repositories import user_repo

        filepath = Path(settings.backup_dir) / filename
        size = filepath.stat().st_size if filepath.exists() else 0

        async with async_session_factory() as db:
            staff = await user_repo.get_active_staff(db)
            audit_user_id = staff[0].id if staff else None
            if audit_user_id:
                await write_audit_log(
                    db,
                    user_id=audit_user_id,
                    action="backup.scheduled.completed",
                    resource_type="database",
                    details={
                        "filename": filename,
                        "size_bytes": size,
                        "triggered_by": triggered_by,
                    },
                )
            await db.commit()
    except Exception:
        logger.exception("Failed to write audit log for scheduled backup")

_scheduler_task: asyncio.Task | None = None


async def _scheduler_loop() -> None:
    """Check once per minute whether a scheduled backup should run."""
    last_run_key: str | None = None

    while True:
        await asyncio.sleep(60)
        try:
            enabled = get_setting("backup_schedule_enabled") == "true"
            if not enabled:
                continue

            frequency = get_setting("backup_schedule_frequency") or "daily"
            hour = int(get_setting("backup_schedule_hour") or "2")
            minute = int(get_setting("backup_schedule_minute") or "0")
            weekday = int(get_setting("backup_schedule_weekday") or "0")

            now = datetime.now(timezone.utc)

            if frequency == "hourly":
                if now.minute != minute:
                    continue
                run_key = now.strftime("%Y-%m-%d-%H")
            elif frequency == "weekly":
                if now.weekday() != weekday or now.hour != hour or now.minute != minute:
                    continue
                run_key = f"{now.strftime('%Y-W%W')}"
            else:  # daily
                if now.hour != hour or now.minute != minute:
                    continue
                run_key = now.strftime("%Y-%m-%d")

            if last_run_key == run_key:
                continue

            last_run_key = run_key
            logger.info("Scheduled %s backup triggered at %s", frequency, now.isoformat())
            from src.services.backup_service import run_backup
            filename = await run_backup(triggered_by="scheduler")
            logger.info("Scheduled backup completed")
            await _audit_scheduled_backup(filename, triggered_by="scheduler")
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
