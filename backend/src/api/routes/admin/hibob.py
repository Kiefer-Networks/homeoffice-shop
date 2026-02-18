import asyncio
import logging

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies.auth import require_admin
from src.api.dependencies.database import async_session_factory, get_db
from src.audit.service import write_audit_log
from src.integrations.hibob.client import HiBobClient
from src.integrations.hibob.sync import sync_employees
from src.models.dto.hibob import (
    HiBobPurchaseSyncLogListResponse,
    HiBobPurchaseSyncLogResponse,
    HiBobSyncLogListResponse,
    HiBobSyncLogResponse,
)
from src.models.orm.user import User
from src.notifications.service import notify_staff_email, notify_staff_slack
from src.services import hibob_service
from src.services.purchase_sync import sync_purchases
from src.services.settings_service import get_setting

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/hibob", tags=["admin-hibob"])

_employee_sync_lock = asyncio.Lock()
_purchase_sync_lock = asyncio.Lock()


async def _guarded_employee_sync(admin_id, ip: str | None) -> None:
    """Acquire the lock, then delegate to the actual sync."""
    async with _employee_sync_lock:
        await _run_employee_sync(admin_id, ip)


async def _guarded_purchase_sync(admin_id, ip: str | None) -> None:
    """Acquire the lock, then delegate to the actual sync."""
    async with _purchase_sync_lock:
        await _run_purchase_sync(admin_id, ip)


async def _run_employee_sync(admin_id, ip: str | None) -> None:
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
                },
                ip_address=ip,
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

            # After successful employee sync, also trigger purchase sync
            if log.status == "completed":
                table_id = get_setting("hibob_purchase_table_id")
                if table_id:
                    purchase_log = await sync_purchases(db, client, triggered_by=admin_id)
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
            logger.exception("Background employee sync failed")


async def _run_purchase_sync(admin_id, ip: str | None) -> None:
    """Run purchase sync in the background with its own DB session."""
    async with async_session_factory() as db:
        try:
            client = HiBobClient()
            purchase_log = await sync_purchases(db, client, triggered_by=admin_id)

            await write_audit_log(
                db, user_id=admin_id, action="admin.hibob.purchase_sync_triggered",
                resource_type="hibob_purchase_sync",
                details={
                    "status": purchase_log.status,
                    "entries_found": purchase_log.entries_found,
                    "matched": purchase_log.matched,
                    "auto_adjusted": purchase_log.auto_adjusted,
                    "pending_review": purchase_log.pending_review,
                },
                ip_address=ip,
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
            logger.exception("Background purchase sync failed")


@router.post("/sync", status_code=202)
async def trigger_sync(
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    if _employee_sync_lock.locked():
        return {"detail": "Sync already in progress"}
    ip = request.client.host if request.client else None
    asyncio.create_task(_guarded_employee_sync(admin.id, ip))
    return {"detail": "Sync started in background"}


@router.get("/sync-log", response_model=HiBobSyncLogListResponse)
async def get_sync_logs(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    items, total = await hibob_service.get_sync_logs(db, page=page, per_page=per_page)
    return {"items": items, "total": total, "page": page, "per_page": per_page}


@router.post("/purchase-sync", status_code=202)
async def trigger_purchase_sync(
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    if _purchase_sync_lock.locked():
        return {"detail": "Purchase sync already in progress"}
    ip = request.client.host if request.client else None
    asyncio.create_task(_guarded_purchase_sync(admin.id, ip))
    return {"detail": "Purchase sync started in background"}


@router.get("/purchase-sync-log", response_model=HiBobPurchaseSyncLogListResponse)
async def get_purchase_sync_logs(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    items, total = await hibob_service.get_purchase_sync_logs(db, page=page, per_page=per_page)
    return {"items": items, "total": total, "page": page, "per_page": per_page}
