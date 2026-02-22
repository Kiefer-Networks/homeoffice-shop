"""Unified background scheduler — single event loop for all periodic tasks.

Schedule:
  - Backup:            configurable (default daily 02:00 UTC)
  - Delivery reminder: daily 08:00 UTC
  - AfterShip sync:    4× daily at 08, 12, 16, 20 UTC
  - HiBob user sync:   configurable (default daily 03:00 UTC)
  - Cart stale cleanup: daily 04:30 UTC
  - HiBob purchases:   configurable (default 04:00 and 16:00 UTC)
"""

import asyncio
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

from src.core.config import settings
from src.core.database import async_session_factory
from src.services.settings_service import get_setting, get_setting_int, load_settings

logger = logging.getLogger(__name__)

_scheduler_task: asyncio.Task | None = None
_last_heartbeat: float = 0.0

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

async def _run_delivery_reminders(now: datetime) -> None:
    delivery_hour = get_setting_int("delivery_reminder_hour", 8)
    if now.hour != delivery_hour:
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

async def _run_aftership_sync(now: datetime) -> None:
    from src.integrations.aftership.client import aftership_client
    if not aftership_client.is_configured:
        return

    raw = get_setting("aftership_sync_hours", "8,12,16,20")
    sync_hours = tuple(int(h.strip()) for h in raw.split(",") if h.strip())
    if now.hour not in sync_hours:
        return

    run_key = f"{now.strftime('%Y-%m-%d')}T{now.hour}"
    if not _should_run("aftership", run_key):
        return

    logger.info("AfterShip scheduled sync triggered")
    from src.integrations.aftership.sync import sync_all_active_orders
    from src.audit.service import write_audit_log
    from src.repositories import user_repo

    result = await sync_all_active_orders()
    logger.info("AfterShip sync result: %s", result)

    # Audit trail for AfterShip sync
    try:
        async with async_session_factory() as db:
            staff = await user_repo.get_active_staff(db)
            if staff:
                await write_audit_log(
                    db,
                    user_id=staff[0].id,
                    action="aftership_sync",
                    resource_type="aftership",
                    details={"result": result},
                )
            await db.commit()
    except Exception:
        logger.exception("Failed to write audit log for AfterShip sync")


# ── Task: HiBob User Sync (every 24h) ───────────────────────────────────────

async def _run_hibob_user_sync(now: datetime) -> None:
    if not settings.hibob_api_key:
        return

    sync_hour = get_setting_int("hibob_user_sync_hour")
    if now.hour != sync_hour:
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

async def _run_cart_cleanup(now: datetime) -> None:
    cleanup_hour = get_setting_int("cart_cleanup_hour", 4)
    cleanup_minute = get_setting_int("cart_cleanup_minute", 30)
    if now.hour != cleanup_hour or now.minute != cleanup_minute:
        return

    run_key = now.strftime("%Y-%m-%d")
    if not _should_run("cart_cleanup", run_key):
        return

    logger.info("Cart stale item cleanup triggered")
    from src.services.cart_service import cleanup_stale_items
    from src.audit.service import write_audit_log
    from src.repositories import user_repo

    async with async_session_factory() as db:
        try:
            removed = await cleanup_stale_items(db)

            # Audit trail for cart cleanup
            staff = await user_repo.get_active_staff(db)
            if staff:
                await write_audit_log(
                    db,
                    user_id=staff[0].id,
                    action="cart_cleanup",
                    resource_type="cart",
                    details={"removed": removed},
                )

            await db.commit()
            logger.info("Cart stale cleanup completed: %d items removed", removed)
        except Exception:
            await db.rollback()
            logger.exception("Cart stale item cleanup failed")


# ── Task: HiBob Purchase Sync (configurable hours) ──────────────────────────

async def _run_hibob_purchase_sync(now: datetime) -> None:
    if not settings.hibob_api_key:
        return

    raw = get_setting("hibob_purchase_sync_hours")
    purchase_sync_hours = tuple(int(h.strip()) for h in raw.split(",") if h.strip())
    if now.hour not in purchase_sync_hours:
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
    global _last_heartbeat
    while True:
        await asyncio.sleep(60)
        _last_heartbeat = time.monotonic()
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
            "AfterShip (configurable), HiBob users (configurable), "
            "cart cleanup (configurable), HiBob purchases (configurable)",
        )


def get_scheduler_health() -> dict:
    """Return scheduler health based on heartbeat recency.

    The scheduler loop runs every 60 seconds. A heartbeat older than
    70 seconds (with 10s grace) indicates the scheduler may be stalled.
    """
    if _scheduler_task is None:
        return {"status": "not_started"}
    if _scheduler_task.done():
        return {"status": "stopped"}
    if _last_heartbeat == 0.0:
        # Task was created but hasn't completed its first loop yet
        return {"status": "starting"}
    elapsed = time.monotonic() - _last_heartbeat
    if elapsed > 70:
        return {"status": "stale", "last_heartbeat_secs_ago": round(elapsed)}
    return {"status": "healthy", "last_heartbeat_secs_ago": round(elapsed)}


def stop_scheduler() -> None:
    global _scheduler_task
    if _scheduler_task and not _scheduler_task.done():
        _scheduler_task.cancel()
        _scheduler_task = None
        logger.info("Unified scheduler stopped")
