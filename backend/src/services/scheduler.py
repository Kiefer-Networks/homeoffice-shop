"""Unified background scheduler — single event loop for all periodic tasks.

Schedule:
  - Backup:           configurable (default daily 02:00 UTC)
  - Delivery reminder: daily 08:00 UTC
  - AfterShip sync:   4× daily at 08, 12, 16, 20 UTC
  - HiBob user sync:  daily 03:00 UTC (every 24h)
  - Cart stale cleanup: daily 04:30 UTC
  - HiBob purchases:  2× daily at 04:00 and 16:00 UTC (every 12h)
"""

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path

from src.core.config import settings
from src.core.database import async_session_factory
from src.services.settings_service import get_setting, load_settings

logger = logging.getLogger(__name__)

_scheduler_task: asyncio.Task | None = None

# ── Dedup keys ───────────────────────────────────────────────────────────────

_last_run: dict[str, str] = {}


def _should_run(task_name: str, run_key: str) -> bool:
    """Return True if this task+key hasn't run yet, and mark it as run."""
    if _last_run.get(task_name) == run_key:
        return False
    _last_run[task_name] = run_key
    return True


# ── Task: Backup ─────────────────────────────────────────────────────────────

async def _run_backup(now: datetime) -> None:
    enabled = get_setting("backup_schedule_enabled") == "true"
    if not enabled:
        return

    frequency = get_setting("backup_schedule_frequency") or "daily"
    hour = int(get_setting("backup_schedule_hour") or "2")
    minute = int(get_setting("backup_schedule_minute") or "0")
    weekday = int(get_setting("backup_schedule_weekday") or "0")

    if frequency == "hourly":
        if now.minute != minute:
            return
        run_key = now.strftime("%Y-%m-%d-%H")
    elif frequency == "weekly":
        if now.weekday() != weekday or now.hour != hour or now.minute != minute:
            return
        run_key = now.strftime("%Y-W%W")
    else:  # daily
        if now.hour != hour or now.minute != minute:
            return
        run_key = now.strftime("%Y-%m-%d")

    if not _should_run("backup", run_key):
        return

    logger.info("Scheduled %s backup triggered", frequency)
    from src.services.backup_service import run_backup
    filename = await run_backup(triggered_by="scheduler")
    logger.info("Scheduled backup completed: %s", filename)

    # Audit
    try:
        from src.audit.service import write_audit_log
        from src.repositories import user_repo

        filepath = Path(settings.backup_dir) / filename
        size = filepath.stat().st_size if filepath.exists() else 0

        async with async_session_factory() as db:
            staff = await user_repo.get_active_staff(db)
            if staff:
                await write_audit_log(
                    db,
                    user_id=staff[0].id,
                    action="backup.scheduled.completed",
                    resource_type="database",
                    details={"filename": filename, "size_bytes": size, "triggered_by": "scheduler"},
                )
            await db.commit()
    except Exception:
        logger.exception("Failed to write audit log for scheduled backup")


# ── Task: Delivery Reminders ─────────────────────────────────────────────────

DELIVERY_REMINDER_HOUR = 8

async def _run_delivery_reminders(now: datetime) -> None:
    if now.hour != DELIVERY_REMINDER_HOUR:
        return

    run_key = now.strftime("%Y-%m-%d")
    if not _should_run("delivery_reminder", run_key):
        return

    logger.info("Delivery reminder check triggered")
    async with async_session_factory() as db:
        await load_settings(db)
        from src.services.delivery_reminder import send_delivery_reminders
        sent = await send_delivery_reminders(db)
        await db.commit()

    if sent:
        logger.info("Sent %d delivery reminder(s)", sent)


# ── Task: AfterShip Tracking ────────────────────────────────────────────────

AFTERSHIP_SYNC_HOURS = (8, 12, 16, 20)

async def _run_aftership_sync(now: datetime) -> None:
    from src.integrations.aftership.client import aftership_client
    if not aftership_client.is_configured:
        return

    if now.hour not in AFTERSHIP_SYNC_HOURS:
        return

    run_key = f"{now.strftime('%Y-%m-%d')}T{now.hour}"
    if not _should_run("aftership", run_key):
        return

    logger.info("AfterShip scheduled sync triggered")
    from src.integrations.aftership.sync import sync_all_active_orders
    result = await sync_all_active_orders()
    logger.info("AfterShip sync result: %s", result)


# ── Task: HiBob User Sync (every 24h) ───────────────────────────────────────

HIBOB_USER_SYNC_HOUR = 3

async def _run_hibob_user_sync(now: datetime) -> None:
    if not settings.hibob_api_key:
        return

    if now.hour != HIBOB_USER_SYNC_HOUR:
        return

    run_key = now.strftime("%Y-%m-%d")
    if not _should_run("hibob_users", run_key):
        return

    logger.info("Scheduled HiBob user sync triggered")
    from src.services.hibob_service import _employee_sync_lock, is_employee_sync_locked

    if is_employee_sync_locked():
        logger.warning("HiBob user sync skipped — already in progress")
        return

    async with _employee_sync_lock:
        from src.integrations.hibob.client import HiBobClient
        from src.integrations.hibob.sync import sync_employees
        from src.audit.service import write_audit_log
        from src.repositories import user_repo
        from src.notifications.service import notify_staff_email

        async with async_session_factory() as db:
            try:
                client = HiBobClient()
                log = await sync_employees(db, client, admin_id=None)

                # Audit — attribute to first admin
                staff = await user_repo.get_active_staff(db)
                if staff:
                    await write_audit_log(
                        db,
                        user_id=staff[0].id,
                        action="hibob.scheduled_sync.completed",
                        resource_type="hibob_sync",
                        details={
                            "status": log.status,
                            "synced": log.employees_synced,
                            "created": log.employees_created,
                            "updated": log.employees_updated,
                            "deactivated": log.employees_deactivated,
                            "error_message": log.error_message,
                            "trigger": "scheduled",
                        },
                    )

                try:
                    if log.status == "failed":
                        await notify_staff_email(
                            db, event="hibob.sync_error",
                            subject="HiBob Scheduled Sync Failed",
                            template_name="hibob_sync_error.html",
                            context={"error_message": log.error_message},
                        )
                    else:
                        await notify_staff_email(
                            db, event="hibob.sync",
                            subject="HiBob Scheduled Sync Complete",
                            template_name="hibob_sync_complete.html",
                            context={
                                "employees_synced": log.employees_synced,
                                "employees_created": log.employees_created,
                                "employees_updated": log.employees_updated,
                                "employees_deactivated": log.employees_deactivated,
                                "error_message": log.error_message,
                            },
                        )
                except Exception:
                    logger.exception("Failed to send HiBob sync notification")

                await db.commit()
                logger.info(
                    "HiBob user sync completed: %d synced, %d created, %d updated, %d deactivated",
                    log.employees_synced, log.employees_created,
                    log.employees_updated, log.employees_deactivated,
                )
            except Exception:
                await db.rollback()
                logger.exception("Scheduled HiBob user sync failed")


# ── Task: Cart Stale Cleanup ─────────────────────────────────────────────────

CART_CLEANUP_HOUR = 4
CART_CLEANUP_MINUTE = 30

async def _run_cart_cleanup(now: datetime) -> None:
    if now.hour != CART_CLEANUP_HOUR or now.minute != CART_CLEANUP_MINUTE:
        return

    run_key = now.strftime("%Y-%m-%d")
    if not _should_run("cart_cleanup", run_key):
        return

    logger.info("Cart stale item cleanup triggered")
    from src.services.cart_service import cleanup_stale_items

    async with async_session_factory() as db:
        try:
            removed = await cleanup_stale_items(db)
            await db.commit()
            logger.info("Cart stale cleanup completed: %d items removed", removed)
        except Exception:
            await db.rollback()
            logger.exception("Cart stale item cleanup failed")


# ── Task: HiBob Purchase Sync (every 12h) ───────────────────────────────────

HIBOB_PURCHASE_SYNC_HOURS = (4, 16)

async def _run_hibob_purchase_sync(now: datetime) -> None:
    if not settings.hibob_api_key:
        return

    if now.hour not in HIBOB_PURCHASE_SYNC_HOURS:
        return

    run_key = f"{now.strftime('%Y-%m-%d')}T{now.hour}"
    if not _should_run("hibob_purchases", run_key):
        return

    table_id = get_setting("hibob_purchase_table_id")
    if not table_id:
        return

    logger.info("Scheduled HiBob purchase sync triggered")
    from src.services.hibob_service import _purchase_sync_lock, is_purchase_sync_locked, _create_sync_log, _mark_sync_failed

    if is_purchase_sync_locked():
        logger.warning("HiBob purchase sync skipped — already in progress")
        return

    async with _purchase_sync_lock:
        from src.integrations.hibob.client import HiBobClient
        from src.services.purchase_sync import sync_purchases
        from src.audit.service import write_audit_log
        from src.repositories import user_repo
        from src.notifications.service import notify_staff_email

        log_id = await _create_sync_log(None)
        async with async_session_factory() as db:
            try:
                client = HiBobClient()
                purchase_log = await sync_purchases(db, client, triggered_by=None, log_id=log_id)

                # Audit
                staff = await user_repo.get_active_staff(db)
                if staff:
                    await write_audit_log(
                        db,
                        user_id=staff[0].id,
                        action="hibob.scheduled_purchase_sync.completed",
                        resource_type="hibob_purchase_sync",
                        details={
                            "status": purchase_log.status,
                            "entries_found": purchase_log.entries_found,
                            "matched": purchase_log.matched,
                            "auto_adjusted": purchase_log.auto_adjusted,
                            "pending_review": purchase_log.pending_review,
                            "error_message": getattr(purchase_log, "error_message", None),
                            "trigger": "scheduled",
                        },
                    )

                if purchase_log.pending_review > 0:
                    try:
                        await notify_staff_email(
                            db, event="hibob.purchase_review",
                            subject="HiBob Purchases Pending Review",
                            template_name="purchase_review_pending.html",
                            context={"count": purchase_log.pending_review},
                        )
                    except Exception:
                        logger.exception("Failed to send purchase review notification")

                await db.commit()
                logger.info(
                    "HiBob purchase sync completed: %d entries, %d matched, %d adjusted, %d pending",
                    purchase_log.entries_found, purchase_log.matched,
                    purchase_log.auto_adjusted, purchase_log.pending_review,
                )
            except Exception:
                await db.rollback()
                await _mark_sync_failed(log_id)
                logger.exception("Scheduled HiBob purchase sync failed")


# ── Main Loop ────────────────────────────────────────────────────────────────

ALL_TASKS = [
    ("backup", _run_backup),
    ("delivery_reminder", _run_delivery_reminders),
    ("aftership", _run_aftership_sync),
    ("hibob_users", _run_hibob_user_sync),
    ("cart_cleanup", _run_cart_cleanup),
    ("hibob_purchases", _run_hibob_purchase_sync),
]


async def _scheduler_loop() -> None:
    """Single event loop — checks every 60s which tasks are due."""
    while True:
        await asyncio.sleep(60)
        now = datetime.now(timezone.utc)

        for task_name, task_fn in ALL_TASKS:
            try:
                await task_fn(now)
            except Exception:
                logger.exception("Scheduler task '%s' failed", task_name)


def start_scheduler() -> None:
    global _scheduler_task
    if _scheduler_task is None or _scheduler_task.done():
        _scheduler_task = asyncio.create_task(_scheduler_loop())
        logger.info(
            "Unified scheduler started — backup, delivery reminders, "
            "AfterShip (%s UTC), HiBob users (%02d UTC), "
            "cart cleanup (%02d:%02d UTC), HiBob purchases (%s UTC)",
            AFTERSHIP_SYNC_HOURS, HIBOB_USER_SYNC_HOUR,
            CART_CLEANUP_HOUR, CART_CLEANUP_MINUTE,
            HIBOB_PURCHASE_SYNC_HOURS,
        )


def stop_scheduler() -> None:
    global _scheduler_task
    if _scheduler_task and not _scheduler_task.done():
        _scheduler_task.cancel()
        _scheduler_task = None
        logger.info("Unified scheduler stopped")
