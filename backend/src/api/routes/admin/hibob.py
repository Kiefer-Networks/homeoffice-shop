from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies.auth import require_admin
from src.api.dependencies.database import get_db
from src.audit.service import write_audit_log
from src.integrations.hibob.client import HiBobClient
from src.integrations.hibob.sync import sync_employees
from src.models.dto.hibob import HiBobSyncLogListResponse, HiBobSyncLogResponse
from src.models.orm.hibob_sync_log import HiBobSyncLog
from src.models.orm.user import User
from src.notifications.service import notify_staff_email, notify_staff_slack

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
