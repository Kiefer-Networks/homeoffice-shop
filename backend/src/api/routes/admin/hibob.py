from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies.auth import require_admin
from src.api.dependencies.database import get_db
from src.audit.service import write_audit_log
from src.integrations.hibob.client import HiBobClient
from src.integrations.hibob.sync import sync_employees
from src.models.dto.hibob import (
    HiBobPurchaseSyncLogListResponse,
    HiBobPurchaseSyncLogResponse,
    HiBobSyncLogListResponse,
    HiBobSyncLogResponse,
)
from src.models.orm.hibob_purchase_sync_log import HiBobPurchaseSyncLog
from src.models.orm.hibob_sync_log import HiBobSyncLog
from src.models.orm.user import User
from src.notifications.service import notify_staff_email, notify_staff_slack
from src.services.purchase_sync import sync_purchases
from src.services.settings_service import get_setting

router = APIRouter(prefix="/hibob", tags=["admin-hibob"])


@router.post("/sync", response_model=HiBobSyncLogResponse)
async def trigger_sync(
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    client = HiBobClient()
    log = await sync_employees(db, client, admin_id=admin.id)

    ip = request.client.host if request.client else None
    await write_audit_log(
        db, user_id=admin.id, action="admin.hibob.sync_triggered",
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

    # After successful employee sync, also trigger purchase sync if configured
    if log.status == "completed":
        table_id = get_setting("hibob_purchase_table_id")
        if table_id:
            purchase_log = await sync_purchases(db, client, triggered_by=admin.id)
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

    return log


@router.get("/sync-log", response_model=HiBobSyncLogListResponse)
async def get_sync_logs(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    from sqlalchemy import func
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
    items = list(result.scalars().all())
    return {"items": items, "total": total, "page": page, "per_page": per_page}


@router.post("/purchase-sync", response_model=HiBobPurchaseSyncLogResponse)
async def trigger_purchase_sync(
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    client = HiBobClient()
    purchase_log = await sync_purchases(db, client, triggered_by=admin.id)

    ip = request.client.host if request.client else None
    await write_audit_log(
        db, user_id=admin.id, action="admin.hibob.purchase_sync_triggered",
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

    return purchase_log


@router.get("/purchase-sync-log", response_model=HiBobPurchaseSyncLogListResponse)
async def get_purchase_sync_logs(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    from sqlalchemy import func

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
    items = list(result.scalars().all())
    return {"items": items, "total": total, "page": page, "per_page": per_page}
