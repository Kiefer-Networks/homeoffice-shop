import asyncio
import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import async_session_factory
from src.audit.service import write_audit_log
from src.integrations.hibob.client import HiBobClient
from src.integrations.hibob.sync import sync_employees
from src.models.orm.hibob_purchase_sync_log import HiBobPurchaseSyncLog
from src.models.orm.hibob_sync_log import HiBobSyncLog
from src.notifications.service import notify_staff_email, notify_staff_slack
from src.services.purchase_sync import sync_purchases
from src.services.settings_service import get_setting

logger = logging.getLogger(__name__)

SYNC_STALE_MINUTES = 30

_employee_sync_lock = asyncio.Lock()
_purchase_sync_lock = asyncio.Lock()


async def guarded_employee_sync(admin_id: UUID, ip: str | None, user_agent: str | None = None) -> None:
    """Acquire the lock, then delegate to the actual sync."""
    async with _employee_sync_lock:
        await _run_employee_sync(admin_id, ip, user_agent)


async def guarded_purchase_sync(admin_id: UUID, ip: str | None, user_agent: str | None = None) -> None:
    """Acquire the lock, then delegate to the actual sync."""
    async with _purchase_sync_lock:
        await _run_purchase_sync(admin_id, ip, user_agent)


def is_employee_sync_locked() -> bool:
    return _employee_sync_lock.locked()


def is_purchase_sync_locked() -> bool:
    return _purchase_sync_lock.locked()


async def is_purchase_sync_running(db: AsyncSession) -> bool:
    """Return whether a purchase sync is currently running."""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=SYNC_STALE_MINUTES)
    result = await db.execute(
        select(HiBobPurchaseSyncLog)
        .where(
            HiBobPurchaseSyncLog.status == "running",
            HiBobPurchaseSyncLog.started_at > cutoff,
        )
        .limit(1)
    )
    return result.scalar_one_or_none() is not None


async def _run_employee_sync(admin_id: UUID, ip: str | None, user_agent: str | None = None) -> None:
    """Run employee + purchase sync in the background with its own DB session."""
    async with async_session_factory() as db:
        try:
            client = HiBobClient()
            log = await sync_employees(db, client, admin_id=admin_id)

            await write_audit_log(
                db, user_id=admin_id, action="admin.hibob.sync_triggered",
                resource_type="hibob_sync",
                details={
                    "status": log.status,
                    "synced": log.employees_synced,
                    "created": log.employees_created,
                    "updated": log.employees_updated,
                    "deactivated": log.employees_deactivated,
                    "error_message": log.error_message,
                },
                ip_address=ip, user_agent=user_agent,
            )

            if log.status == "failed":
                await notify_staff_email(
                    db, event="hibob.sync_error",
                    subject="HiBob Sync Failed",
                    template_name="hibob_sync_error.html",
                    context={"error_message": log.error_message},
                )
                await notify_staff_slack(
                    db, event="hibob.sync_error",
                    text=f"HiBob sync failed: {log.error_message}",
                )
            else:
                await notify_staff_email(
                    db, event="hibob.sync",
                    subject="HiBob Sync Complete",
                    template_name="hibob_sync_complete.html",
                    context={
                        "employees_synced": log.employees_synced,
                        "employees_created": log.employees_created,
                        "employees_updated": log.employees_updated,
                        "employees_deactivated": log.employees_deactivated,
                        "error_message": log.error_message,
                    },
                )
                await notify_staff_slack(
                    db, event="hibob.sync",
                    text=f"HiBob sync completed: {log.employees_synced} synced, "
                         f"{log.employees_created} created, {log.employees_updated} updated",
                )

            purchase_log_id = None
            if log.status == "completed":
                table_id = get_setting("hibob_purchase_table_id")
                if table_id:
                    purchase_log_id = await _create_sync_log(admin_id)
                    purchase_log = await sync_purchases(db, client, triggered_by=admin_id, log_id=purchase_log_id)
                    if purchase_log.pending_review > 0:
                        await notify_staff_email(
                            db, event="hibob.purchase_review",
                            subject="HiBob Purchases Pending Review",
                            template_name="purchase_review_pending.html",
                            context={"count": purchase_log.pending_review},
                        )
                        await notify_staff_slack(
                            db, event="hibob.purchase_review",
                            text=f"There are {purchase_log.pending_review} HiBob purchases pending review.",
                        )

            await db.commit()
        except Exception:
            await db.rollback()
            if purchase_log_id:
                await _mark_sync_failed(purchase_log_id)
            logger.exception("Background employee sync failed")


async def _create_sync_log(triggered_by: UUID) -> UUID:
    """Create a sync log entry in a separate committed transaction.

    This ensures the 'running' status is visible to all workers immediately.
    """
    async with async_session_factory() as status_db:
        entry = HiBobPurchaseSyncLog(status="running", triggered_by=triggered_by)
        status_db.add(entry)
        await status_db.commit()
        return entry.id


async def _mark_sync_failed(log_id: UUID) -> None:
    """Mark a sync log as failed in a separate transaction (for error recovery)."""
    async with async_session_factory() as err_db:
        log = await err_db.get(HiBobPurchaseSyncLog, log_id)
        if log and log.status == "running":
            log.status = "failed"
            log.error_message = "Unexpected error in background task"
            log.completed_at = datetime.now(timezone.utc)
            await err_db.commit()


async def _run_purchase_sync(admin_id: UUID, ip: str | None, user_agent: str | None = None) -> None:
    """Run purchase sync in the background with its own DB session."""
    log_id = await _create_sync_log(admin_id)
    async with async_session_factory() as db:
        try:
            client = HiBobClient()
            purchase_log = await sync_purchases(db, client, triggered_by=admin_id, log_id=log_id)

            await write_audit_log(
                db, user_id=admin_id, action="admin.hibob.purchase_sync_triggered",
                resource_type="hibob_purchase_sync",
                details={
                    "status": purchase_log.status,
                    "entries_found": purchase_log.entries_found,
                    "matched": purchase_log.matched,
                    "auto_adjusted": purchase_log.auto_adjusted,
                    "pending_review": purchase_log.pending_review,
                    "error_message": getattr(purchase_log, "error_message", None),
                },
                ip_address=ip, user_agent=user_agent,
            )

            if purchase_log.pending_review > 0:
                await notify_staff_email(
                    db, event="hibob.purchase_review",
                    subject="HiBob Purchases Pending Review",
                    template_name="purchase_review_pending.html",
                    context={"count": purchase_log.pending_review},
                )
                await notify_staff_slack(
                    db, event="hibob.purchase_review",
                    text=f"There are {purchase_log.pending_review} HiBob purchases pending review.",
                )

            await db.commit()
        except Exception:
            await db.rollback()
            await _mark_sync_failed(log_id)
            logger.exception("Background purchase sync failed")


async def get_sync_logs(
    db: AsyncSession, *, page: int = 1, per_page: int = 20,
) -> tuple[list[HiBobSyncLog], int]:
    count_result = await db.execute(
        select(func.count()).select_from(HiBobSyncLog)
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        select(HiBobSyncLog)
        .order_by(HiBobSyncLog.started_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    return list(result.scalars().all()), total


async def get_purchase_sync_logs(
    db: AsyncSession, *, page: int = 1, per_page: int = 20,
) -> tuple[list[HiBobPurchaseSyncLog], int]:
    count_result = await db.execute(
        select(func.count()).select_from(HiBobPurchaseSyncLog)
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        select(HiBobPurchaseSyncLog)
        .order_by(HiBobPurchaseSyncLog.started_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    return list(result.scalars().all()), total
